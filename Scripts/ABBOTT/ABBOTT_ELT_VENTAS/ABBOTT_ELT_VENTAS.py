# -*- coding: utf-8 -*-
import os
import sys
import json
import requests
import time
import getpass
from dotenv import load_dotenv
from urllib.parse import urlparse, unquote
import msal
import pandas as pd
from sqlalchemy import create_engine, text
import sqlalchemy as sa

# ----------------------------------------------------------------------
# 1. Configuración de Archivos y Rutas
# ----------------------------------------------------------------------

# Rutas de los archivos de entorno (ABSOLUTAS, ASUMIENDO WINDOWS C:\Scripts)
BASE_CONFIG_DIR = "C:\\Scripts"
APP_CONFIG_DIR = os.path.join(BASE_CONFIG_DIR, "ABBOTT")
ENV_CONFIG_FILENAME = "config.env"
ENV_CONFIG_PATH = os.path.join(BASE_CONFIG_DIR, ENV_CONFIG_FILENAME)

# Variables ESPERADAS en config.env con los nuevos nombres:
CONFIG_VARS = {
    "CLIENT_ID_AZURE": "ID de la aplicación Azure",
    "TENANT_ID_MICROSOFT": "ID de Inquilino/Directorio",
    "USUARIO_MICROSOFT": "Correo de usuario (UPN)",
    "CONTRASENA_MICROSOFT": "Contraseña de usuario",
    "URL_SHAREPOINT_ABBOTT_ETL_VENTAS": "URL completa del archivo de SharePoint",
    "SERVER_SQL_07": "Nombre del servidor SQL (e.g., SERVER_SQL_07)",
    "USER_SQL": "Usuario de SQL Server",
    "PASSWORD_SQL": "Contraseña de SQL Server",
    "DATABASE_ABBOTT_UTILES": "Nombre de la base de datos",
    "ODBC_DRIVER": "Nombre del driver ODBC de SQL Server (ej: ODBC Driver 17 for SQL Server)",
}

# Scope de la API de Microsoft Graph
GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]

# ----------------------------------------------------------------------
# 2. Lógica de Carga de Configuración
# ----------------------------------------------------------------------

def load_config():
    """Carga todas las variables desde config.env y las valida."""
    print(f"⏳ Cargando configuración desde: {ENV_CONFIG_PATH}")
    
    if not os.path.exists(ENV_CONFIG_PATH):
        print(f"❌ ERROR FATAL: El archivo de configuración '{ENV_CONFIG_FILENAME}' no fue encontrado en la ruta esperada.")
        print("   Por favor, ejecuta el script .bat para iniciar la configuración.")
        sys.exit(1)

    load_dotenv(ENV_CONFIG_PATH, override=True)
    
    config = {}
    missing_vars = []
    
    for var, desc in CONFIG_VARS.items():
        value = os.getenv(var)
        if not value:
            missing_vars.append(f" - {var} ({desc})")
        config[var] = value
        
    if missing_vars:
        print("❌ ERROR DE CONFIGURACIÓN: Faltan las siguientes variables obligatorias en el archivo config.env:")
        for var in missing_vars:
            print(var)
        print("\nPor favor, revisa y edita el archivo manualmente o ejecuta el script .bat de nuevo.")
        sys.exit(1)
        
    print("✅ Configuración cargada con éxito.")
    return config

# ----------------------------------------------------------------------
# 3. Funciones de Utilidad y ETL
# ----------------------------------------------------------------------

def extract_paths_from_url(full_url):
    """
    Analiza la URL de SharePoint para extraer el host, el path del sitio, el nombre
    del Drive, la ruta del archivo dentro de la biblioteca, y el nombre del archivo.
    """
    decoded_url = unquote(full_url)
    parsed = urlparse(decoded_url)
    host = parsed.netloc

    path_parts = parsed.path.strip('/').split('/')
    site_path_segments = []
    drive_name = None
    file_path_segments = []
    
    # Lógica para URLs de sitios (con /sites/) o URLs raíz
    if 'sites' in path_parts:
        try:
            sites_index = path_parts.index('sites')
            site_path_segments = path_parts[sites_index : sites_index + 2]
            drive_name_start_index = sites_index + 2
            if len(path_parts) > drive_name_start_index:
                drive_name = path_parts[drive_name_start_index]
                file_path_segments = path_parts[drive_name_start_index + 1:]
        except (ValueError, IndexError):
             raise ValueError("La URL no sigue el patrón esperado (e.g., /sites/nombre/biblioteca/...).")
    else:
        # Para sitios raíz 
        if path_parts and path_parts[0]:
            drive_name = path_parts[0]
            file_path_segments = path_parts[1:]
        else:
             drive_name = "Documentos"
             file_path_segments = []

        site_path_segments = [] 

    if not drive_name:
        raise ValueError("No se pudo inferir el nombre de la biblioteca de documentos (Drive Name) de la URL.")

    # **CAMBIO CRÍTICO: Extraemos el nombre del archivo para la descarga**
    file_name = file_path_segments[-1] if file_path_segments else ""
    if not file_name:
        raise ValueError("No se pudo inferir el nombre del archivo de la URL.")
    
    site_path = '/' + '/'.join(site_path_segments) if site_path_segments else '/'
    file_path_for_graph = '/'.join(file_path_segments)
    
    print(f"   > Drive inferido (inicial): {drive_name}")
    print(f"   > Nombre del archivo detectado: {file_name}")
    
    return host, site_path, drive_name, file_path_for_graph, file_name

def get_site_and_drive_ids(headers, host, site_path, initial_drive_name):
    """Obtiene el site_id y drive_id."""
    print(f"\n⏳ Buscando Site ID para el host/path: {host}{site_path}")
    
    # 1. Obtener Site ID
    if site_path.strip() == '/':
        site_lookup_url = f"https://graph.microsoft.com/v1.0/sites/{host}"
    else:
        site_lookup_url = f"https://graph.microsoft.com/v1.0/sites/{host}:/{site_path}"

    resp_site = requests.get(site_lookup_url, headers=headers)
    resp_site.raise_for_status()
    site_id = resp_site.json()["id"]
    print(f"✅ Site ID obtenido: {site_id}")
    
    # 2. Obtener Drives disponibles
    resp_drives = requests.get(f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives", headers=headers)
    resp_drives.raise_for_status()
    drives_data = resp_drives.json().get("value", [])
    available_drives = {d.get("name"): d["id"] for d in drives_data if d.get("name") and d.get("id")}
    
    # 3. Verificar si el nombre inferido es correcto
    if initial_drive_name in available_drives:
        drive_name = initial_drive_name
        drive_id = available_drives[drive_name]
        print(f"✅ Drive ID obtenido: {drive_id} (Biblioteca: '{drive_name}')")
        return site_id, drive_id, drive_name
    
    # 4. Corrección automática: Documentos compartidos -> Documentos
    if initial_drive_name.lower().replace(' ', '') == 'documentoscompartidos' and 'Documentos' in available_drives:
        potential_name_fix = 'Documentos'
        drive_name = potential_name_fix
        drive_id = available_drives[drive_name]
        print(f"⚠️ Drive inferido ('{initial_drive_name}') no encontrado. Usando: '{drive_name}'")
        return site_id, drive_id, drive_name
        
    # 5. Fallback a selección interactiva (necesario si la inferencia falla)
    print(f"\n❌ El Drive inferido ('{initial_drive_name}') no se encontró. Nombres encontrados: {list(available_drives.keys())}")
    print("Por favor, selecciona el número de la Biblioteca de Documentos correcta:")
    
    drive_options = list(available_drives.keys())
    for i, name in enumerate(drive_options):
        print(f"   [{i+1}] {name}")
        
    while True:
        try:
            selection = input("Introduce el número de la opción deseada (1, 2, 3...): ").strip()
            choice_index = int(selection) - 1
            if 0 <= choice_index < len(drive_options):
                chosen_drive_name = drive_options[choice_index]
                drive_id = available_drives[chosen_drive_name]
                print(f"✅ Drive seleccionado: '{chosen_drive_name}'")
                return site_id, drive_id, chosen_drive_name
            else:
                print("⚠️ Número inválido. Por favor, introduce un número de la lista.")
        except ValueError:
            print("⚠️ Entrada inválida. Por favor, introduce solo el número (ej: 1).")
        except EOFError:
             print("\nOperación cancelada por el usuario.")
             sys.exit(1)

def download_sharepoint_file_graph(headers, site_id, drive_id, file_path, download_to):
    """Descarga el archivo usando la ruta relativa del Drive mediante Graph API."""
    
    # Esto asegura que el directorio exista, aunque en este caso es el mismo directorio del script.
    os.makedirs(os.path.dirname(download_to) or '.', exist_ok=True) 
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root:/{file_path}:/content"
    
    response = requests.get(url, headers=headers, stream=True, allow_redirects=True)
    response.raise_for_status()
    
    with open(download_to, 'wb') as file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file.write(chunk)
    
    print(f"\n🎉 ¡Descarga Completa! El archivo se ha guardado en:")
    print(f"   > {os.path.abspath(download_to)}")
    return download_to

def get_sql_engine(config):
    """Crea y retorna un motor de SQLAlchemy para la conexión a SQL Server."""
    server = config["SERVER_SQL_07"]
    database = config["DATABASE_ABBOTT_UTILES"]
    username = config["USER_SQL"]
    password = config["PASSWORD_SQL"]
    # Utiliza el driver cargado de la configuración
    driver = config["ODBC_DRIVER"]

    # Cadena de conexión usando el driver ODBC de SQL Server
    connection_string = f"mssql+pyodbc://{username}:{password}@{server}/{database}?driver={driver.replace(' ', '+')}"
    
    try:
        engine = create_engine(connection_string, echo=False)
        # Intenta una conexión para verificar credenciales y driver
        with engine.connect():
            print("✅ Conexión a SQL Server exitosa.")
        return engine
    except Exception as e:
        # Se actualiza el mensaje de error para ser más específico con el driver usado
        print(f"❌ ERROR: No se pudo conectar a SQL Server.")
        print(f"Asegúrate de tener instalados 'pyodbc', 'sqlalchemy' y el driver ODBC '{driver}' en tu sistema.")
        print(f"Detalles: {e}")
        sys.exit(1)

def process_and_load_data(config, file_path, engine):
    """
    Realiza la transformación (unpivot y limpieza) y carga los datos a SQL Server.
    """
    
    print("\n--- 📊 PROCESAMIENTO ETL (Transformación y Carga) ---")
    try:
        if file_path.lower().endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_path)
        elif file_path.lower().endswith(('.csv', '.txt')):
             df = pd.read_csv(file_path, sep='\t')
        else:
            print(f"❌ ERROR: Tipo de archivo no compatible o no detectado: {file_path}. Intente usar .xlsx o .csv.")
            sys.exit(1)
            
        df.columns = df.columns.astype(str).str.strip().str.replace('\ufeff', '')
        print(f"✅ Archivo leído con éxito. Filas iniciales: {len(df)}")

    except Exception as e:
        print(f"❌ ERROR al leer el archivo '{file_path}'. Asegúrate de que el formato y las columnas sean correctos.")
        print(f"Detalles: {e}")
        sys.exit(1)
        
    # 1. Renombrar columnas fijas
    COLUMNAS_FIJAS = {
        'CADENA': 'Cadena',
        'ID_POS': 'IdPos',
        'POS_NAME': 'PosName',
        'CATEGORY': 'Category'
    }
    
    columns_to_rename = {k: v for k, v in COLUMNAS_FIJAS.items() if k in df.columns}
    df.rename(columns=columns_to_rename, inplace=True)
    
    fixed_cols = list(COLUMNAS_FIJAS.values())
    month_cols = [col for col in df.columns if col not in fixed_cols]
    
    if len(fixed_cols) != 4 or not month_cols:
         print("❌ ERROR: Faltan columnas fijas o no se detectaron columnas de meses para hacer el unpivot.")
         print(f"Columnas detectadas: {list(df.columns)}")
         sys.exit(1)

    print(f"   > Columnas fijas: {fixed_cols}")
    print(f"   > Columnas de meses detectadas ({len(month_cols)}): {month_cols[:5]}...")

    # 2. Hacer el Unpivot (Melt)
    df_melted = pd.melt(
        df, 
        id_vars=fixed_cols,
        value_vars=month_cols,
        var_name='Mes',
        value_name='TotalVenta'
    )
    
    # 3. Limpieza y Creación de CategoryFinal
    df_melted['Category'] = df_melted['Category'].astype(str).str.strip()
    
    def calculate_category_final(category):
        category = str(category).strip()
        if category in ('IMF', 'Mom'):
            return 'Similac'
        elif category == 'Medical':
            return 'Otros'
        else:
            return category
            
    df_melted['CategoryFinal'] = df_melted['Category'].apply(calculate_category_final)
    df_melted['TotalVenta'] = pd.to_numeric(df_melted['TotalVenta'], errors='coerce').fillna(0)
    
    df_final = df_melted[['Cadena', 'IdPos', 'PosName', 'Category', 'Mes', 'TotalVenta', 'CategoryFinal']]
    
    print(f"✅ Transformación (Unpivot) completada. Filas finales: {len(df_final)}")
    
    # 4. Carga a SQL Server - ENFOQUE MANUAL POR LOTES
    TABLE_NAME = "##TmpTBL_VentasSellOut_Abbott"
    print(f"\n⏳ Insertando datos en la tabla temporal: {TABLE_NAME}...")
    
    try:
        # Crear la tabla primero
        with engine.connect() as conn:
            conn.execute(text(f"""
                IF OBJECT_ID('tempdb..{TABLE_NAME}') IS NOT NULL
                    DROP TABLE {TABLE_NAME}
                    
                CREATE TABLE {TABLE_NAME} (
                    Cadena VARCHAR(255),
                    IdPos VARCHAR(50),
                    PosName VARCHAR(255),
                    Category VARCHAR(50),
                    Mes VARCHAR(50),
                    TotalVenta FLOAT,
                    CategoryFinal VARCHAR(50)
                )
            """))
            conn.commit()
        
        # Insertar en lotes de 10000 registros
        batch_size = 10000
        total_rows = len(df_final)
        
        for i in range(0, total_rows, batch_size):
            batch = df_final.iloc[i:i+batch_size]
            batch.to_sql(
                TABLE_NAME, 
                con=engine, 
                if_exists='append', 
                index=False
            )
            print(f"   > Lote insertado: {min(i+batch_size, total_rows)}/{total_rows} registros")
            
        print(f"🎉 ¡Carga a {TABLE_NAME} exitosa! {total_rows} registros insertados.")
        
    except Exception as e:
        print(f"❌ ERROR FATAL al insertar datos en SQL Server.")
        print(f"Detalles: {e}")
        sys.exit(1)
    
    return TABLE_NAME

# ----------------------------------------------------------------------
# 4. Función Principal
# ----------------------------------------------------------------------

def main():
    """
    Función principal: carga la config, realiza la autenticación ROPC, descarga,
    procesa datos, carga a SQL, espera input y ejecuta el SP.
    """
    
    # 1. Cargar Configuración
    config = load_config()
    
    # 2. Preparar Variables
    client_id = config["CLIENT_ID_AZURE"]
    tenant_id = config["TENANT_ID_MICROSOFT"]
    username = config["USUARIO_MICROSOFT"]
    password = config["CONTRASENA_MICROSOFT"]
    sharepoint_url = config["URL_SHAREPOINT_ABBOTT_ETL_VENTAS"]
    
    # Obtener la ruta del directorio del script actual.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 3. Obtener paths de SharePoint
    try:
        host, site_path, initial_drive_name, file_path, file_name = extract_paths_from_url(sharepoint_url)
    except ValueError as e:
        print(f"❌ ERROR DE URL: {e}")
        print(f"Por favor, corrige URL_SHAREPOINT_ABBOTT_ETL_VENTAS en {ENV_CONFIG_PATH} y vuelve a intentarlo.")
        sys.exit(1)
    
    # Construir la ruta de descarga final.
    download_path = os.path.join(script_dir, file_name)
    print(f"   > Ruta de descarga final (Directorio del script + Nombre del archivo): {download_path}")

    # 4. Autenticación ROPC
    print(f"\n--- 🔑 AUTENTICACIÓN DE MICROSOFT (Usuario: {username}) ---")
    print("⚠️ Recuerda: ROPC FALLARÁ si la cuenta tiene Autenticación Multifactor (MFA) habilitada.")
    
    access_token = None
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app = msal.PublicClientApplication(client_id, authority=authority)
    
    print("⏳ Intentando obtener el Token de Acceso con ROPC...")

    try:
        # Autenticación directa con las credenciales cargadas de config.env
        result = app.acquire_token_by_username_password(username=username, password=password, scopes=GRAPH_SCOPE)

        if "access_token" in result:
            access_token = result["access_token"]
            print("✅ Token de Acceso obtenido con éxito.")
        else:
            error_description = result.get('error_description', 'Error desconocido.')
            print("❌ ERROR DE AUTENTICACIÓN ROPC.")
            print(f"Detalles del Error: {error_description}")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Ocurrió un error inesperado durante la autenticación: {e}")
        sys.exit(1)
    
    if access_token is None:
        print("❌ La autenticación falló. Saliendo.")
        sys.exit(1)


    # 5. Descargar el Archivo de SharePoint usando Graph API
    print(f"\n⏳ Iniciando descarga usando Microsoft Graph API para:\n   > {sharepoint_url}")

    try:
        headers = { 'Authorization': f'Bearer {access_token}' }
        # Obtener IDs (incluye la lógica de selección interactiva de Drive)
        site_id, drive_id, final_drive_name = get_site_and_drive_ids(headers, host, site_path, initial_drive_name)
        
        # Descargar el archivo
        download_path = download_sharepoint_file_graph(headers, site_id, drive_id, file_path, download_path)

    except requests.exceptions.HTTPError as e:
        print(f"\n❌ ERROR DE LA API DE MICROSOFT GRAPH (HTTP {e.response.status_code}):")
        try:
            error_details = e.response.json().get('error', {})
            print(f"   Mensaje: {error_details.get('message', 'No hay mensaje detallado.')}")
        except json.JSONDecodeError:
             print(f"   Respuesta del Servidor (inicio): {e.response.text[:100]}...")
        print("\nAsegúrate de que la URL de SharePoint sea correcta y que la cuenta tenga los permisos delegados necesarios.")
        sys.exit(1)
    except Exception as e:
         print(f"\n❌ ERROR INESPERADO: {e}")
         sys.exit(1)

    
    # 6. Conexión a SQL Server
    engine = get_sql_engine(config)
    
    # 7. Procesar y Cargar Datos
    temp_table_name = process_and_load_data(config, download_path, engine)

    # 8. Ejecutar Stored Procedure Final
    print("\n--- 🚀 EJECUCIÓN DEL STORED PROCEDURE FINAL ---")
    SP_NAME = "spAbbottEtlVentasSellOut"
    print(f"⏳ Ejecutando Stored Procedure: {SP_NAME}...")
    try:
        # Se asume que el SP toma la tabla temporal como base para su proceso.
        # Usa text() para ejecutar comandos SQL directos, como la llamada a un SP.
        with engine.connect() as connection:
            # Ejemplo de ejecución simple. Adapta esto si el SP requiere parámetros.
            connection.execute(text(f"EXEC {SP_NAME}")) 
            connection.commit()
        print(f"🎉 ¡Ejecución del SP '{SP_NAME}' completada con éxito!")
    except Exception as e:
        print(f"❌ ERROR al ejecutar el Stored Procedure '{SP_NAME}'.")
        print(f"Detalles: {e}")
        # El script continúa para intentar la limpieza.
        
    # 9. Limpieza: Eliminar el archivo descargado
    print(f"\n⏳ Eliminando el archivo de descarga: {download_path}...")
    try:
        os.remove(download_path)
        print("✅ Archivo eliminado con éxito.")
    except Exception as e:
        print(f"⚠️ ADVERTENCIA: No se pudo eliminar el archivo '{download_path}'.")
        print(f"Detalles: {e}")

    print("\n--- ✅ PROCESO ABBOTT ETL COMPLETO ---")


if __name__ == "__main__":
    main()
