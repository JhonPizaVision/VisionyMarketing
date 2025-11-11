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
    # NOTA: RUTA_DESCARGA se ha ELIMINADO de la configuración.
    # El script ahora guardará el archivo en el mismo directorio donde se ejecuta.
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
# 3. Funciones de Utilidad y ETL (Adaptadas a los nuevos nombres de ENV)
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

# ----------------------------------------------------------------------
# 4. Función Principal
# ----------------------------------------------------------------------

def main():
    """
    Función principal: carga la config, realiza la autenticación ROPC y descarga.
    """
    
    # 1. Cargar Configuración
    config = load_config()
    
    # 2. Preparar Variables (Nuevos Nombres)
    client_id = config["CLIENT_ID_AZURE"]
    tenant_id = config["TENANT_ID_MICROSOFT"]
    username = config["USUARIO_MICROSOFT"]
    password = config["CONTRASENA_MICROSOFT"]
    sharepoint_url = config["URL_SHAREPOINT_ABBOTT_ETL_VENTAS"]
    
    # **CAMBIO CLAVE:** Obtener la ruta del directorio del script actual.
    # __file__ es la ruta del script; dirname() obtiene el directorio.
    # El archivo de descarga final se construirá más abajo.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 3. Obtener paths de SharePoint
    try:
        host, site_path, initial_drive_name, file_path, file_name = extract_paths_from_url(sharepoint_url)
    except ValueError as e:
        print(f"❌ ERROR DE URL: {e}")
        print(f"Por favor, corrige URL_SHAREPOINT_ABBOTT_ETL_VENTAS en {ENV_CONFIG_PATH} y vuelve a intentarlo.")
        sys.exit(1)
    
    # **CAMBIO CLAVE:** Construir la ruta de descarga final.
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
        # Se pasa la ruta de descarga ya calculada (directorio del script + nombre del archivo)
        download_sharepoint_file_graph(headers, site_id, drive_id, file_path, download_path)

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


if __name__ == "__main__":
    main()
