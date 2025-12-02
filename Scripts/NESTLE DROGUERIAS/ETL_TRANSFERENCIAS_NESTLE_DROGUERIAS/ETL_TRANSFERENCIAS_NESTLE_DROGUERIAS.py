import logging
from datetime import datetime, date
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
from dotenv import load_dotenv
import glob
import pandas as pd
import sys
from office365.sharepoint.client_context import ClientContext
from office365.runtime.auth.user_credential import UserCredential
import io
import numpy as np
from sqlalchemy import text
import sqlalchemy
import urllib
import requests

# Configuración de logging
def configurar_logging():
    """Configura el sistema de logging para el script, creando un archivo nuevo por ejecución con timestamp"""
    # Generar nombre del archivo con timestamp
    log_filename = f"etl_transferencias.log"

    handler_console = logging.StreamHandler(sys.stdout)
    handler_console.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    handler_console.stream.reconfigure(encoding='utf-8')

    handler_file = logging.FileHandler(log_filename, mode='w', encoding='utf-8')  # 'w' para sobrescribir cada vez
    handler_file.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    logging.basicConfig(
        level=logging.INFO,
        handlers=[
            handler_file,
            handler_console
        ]
    )
    return logging.getLogger(__name__)

logger = configurar_logging()

def configurar_entorno(env_paths=None):
    """
    Carga y valida las variables de entorno necesarias desde uno o varios archivos .env

    Args:
        env_paths (list or None): Lista de rutas de archivos .env a cargar en orden.
                                  Si es None, carga ["ETL_TRANSFERENCIAS.env"]

    Returns:
        dict: Diccionario con las variables requeridas cargadas
    """
    if env_paths is None:
        env_paths = ["config.env"]

    # Cargar todos los archivos .env
    for env_file in env_paths:
        env_path = os.path.abspath(env_file)
        if not os.path.isfile(env_path):
            logger.error(f"El archivo .env no existe en: {env_path}")
            raise FileNotFoundError(f"El archivo .env no existe en: {env_path}")

        load_dotenv(dotenv_path=env_path, override=True)
        logger.info(f"Cargado .env: {env_path}")

    # Validar las variables requeridas
    required_vars = [
                     # CLIENTE
                      "URL_TRANSFERENCIAS_NESTLE_DROGUERIAS"
                     ,"USER_URL_TRANSFERENCIAS_NESTLE_DROGUERIAS"
                     ,"PASSWORD_URL_TRANSFERENCIAS_NESTLE_DROGUERIAS"
                     # SHAREPOINT
                     ,"SHAREPOINT_FILE_PATH"
                     ,"CONTRASENA_MICROSOFT"
                     ,"SHAREPOINT_SITE_DOCUMENTOS_CLIENTES"
                     ,"USUARIO_MICROSOFT"
                     #AZURE
                     ,"CLIENT_ID_AZURE"
                     ,"CLIENT_SECRET_AZURE"
                     ,"TENANT_ID_MICROSOFT"
                     #SQL
                     ,"DATABASE_U_D_NESTLE_DROGUERIAS"
                     ,"PASSWORD_SQL"
                     ,"SERVER_SQL_15"
                     ,"USER_SQL"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"Variables de entorno faltantes: {', '.join(missing_vars)}")
        raise EnvironmentError(f"Variables de entorno faltantes: {', '.join(missing_vars)}")

    return {
        # CLIENTE
        "URL_VENTAS": os.getenv("URL_TRANSFERENCIAS_NESTLE_DROGUERIAS"),
        "USER_URL": os.getenv("USER_URL_TRANSFERENCIAS_NESTLE_DROGUERIAS"),
        "PASSWORD_URL": os.getenv("PASSWORD_URL_TRANSFERENCIAS_NESTLE_DROGUERIAS"),
        # SHAREPOINT
        "SHAREPOINT_FILE_PATH": os.getenv("SHAREPOINT_FILE_PATH") + "Nestle/NESTLE%20DROGUERIAS/ETL/TRANSFERENCIAS/Parametrizacion.xlsx",
        "SHAREPOINT_PASS": os.getenv("CONTRASENA_MICROSOFT"),
        "SHAREPOINT_SITE_DOCUMENTOS_CLIENTES": os.getenv("SHAREPOINT_SITE_DOCUMENTOS_CLIENTES"),
        "SHAREPOINT_USER": os.getenv("USUARIO_MICROSOFT"),
        #SQL
        "DATABASE_U_D_NESTLE_DROGUERIAS": os.getenv("DATABASE_U_D_NESTLE_DROGUERIAS"),
        "PASSWORD_SQL": os.getenv("PASSWORD_SQL"),
        "SERVER_SQL_15": os.getenv("SERVER_SQL_15"),
        "USER_SQL": os.getenv("USER_SQL"),
    }

def configurar_navegador(download_dir):
    """Configura y retorna una instancia del navegador Chrome"""
    chrome_options = Options()

    # Headless moderno
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    # User agent que simula un navegador real
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.5735.133 Safari/537.36"
    )

    # Preferencias de descarga
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "profile.default_content_settings.popups": 0
    }
    chrome_options.add_experimental_option("prefs", prefs)

    # Ocultar que es un navegador automatizado
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    service = Service()
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Ocultar el flag navigator.webdriver
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
        Object.defineProperty(navigator, 'webdriver', {
          get: () => undefined
        });
        """
    })

    return driver

def esperar_descarga_completa(download_dir, timeout=180, archivo_previo=None):
    """
    Espera que desaparezcan los archivos temporales y aparezca uno nuevo completo.
    
    Args:
        download_dir: Directorio de descargas
        timeout: Tiempo máximo de espera
        archivo_previo: Archivo previo para evitar duplicados
    
    Returns:
        str: Ruta del nuevo archivo descargado
    """
    logger.info("Esperando que termine la descarga...")
    start_time = time.time()
    last_temp_file = None
    
    while time.time() - start_time < timeout:
        temp_files = glob.glob(os.path.join(download_dir, "*.crdownload")) + \
                    glob.glob(os.path.join(download_dir, "*.tmp"))
        
        if temp_files:
            last_temp_file = temp_files[0]
        
        complete_files = [
            f for f in glob.glob(os.path.join(download_dir, "*"))
            if not (f.endswith(".crdownload") or f.endswith(".tmp"))
        ]
        
        if not temp_files and complete_files:
            downloaded_file = max(complete_files, key=os.path.getctime)
            
            if archivo_previo is None or downloaded_file != archivo_previo:
                logger.info(f" Archivo descargado: {downloaded_file}")
                return downloaded_file
        
        time.sleep(2)
    
    error_msg = f"Timeout: Descarga no completada en {timeout} segundos."
    if last_temp_file:
        error_msg += f" Último archivo temporal: {last_temp_file}"
    logger.error(error_msg)
    raise TimeoutError(error_msg)

def limpiar_descargas(download_dir, excluir=None):
    """
    Limpia el directorio de descargas eliminando todos los archivos,
    excepto los indicados en `excluir`.

    Args:
        download_dir (str): Ruta del directorio.
        excluir (list, optional): Lista de nombres de archivo que no deben eliminarse.
    """
    if excluir is None:
        excluir = []

    if not os.path.exists(download_dir):
        logger.info(f"Creando directorio: {download_dir}")
        os.makedirs(download_dir)
        return

    archivos = os.listdir(download_dir)
    if not archivos:
        logger.info("El directorio ya está vacío")
        return

    for archivo in archivos:
        if archivo in excluir:
            logger.info(f"Excluido de eliminación: {archivo}")
            continue

        file_path = os.path.join(download_dir, archivo)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
                logger.info(f"Eliminado: {file_path}")
        except Exception as e:
            logger.error(f"Error eliminando {file_path}: {e}")

def proceso_selenium(download_dir, credenciales):
    """Ejecuta todo el proceso de automatización con Selenium"""
    logger.info("Iniciando proceso Selenium")
    driver = configurar_navegador(download_dir)
    
    try:
        limpiar_descargas(download_dir)
        
        # Navegación y login
        driver.get(credenciales["URL_VENTAS"])
        wait = WebDriverWait(driver, 60)

        logger.info("Realizando login...")
        wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="username"]'))).send_keys(credenciales["USER_URL"])
        wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="password"]'))).send_keys(credenciales["PASSWORD_URL"])
        wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="autenticar"]/div[4]/p/button'))).click()

        # Descargar primer archivo
        logger.info("Descargando pedidos realizados...")
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="navToggle"]'))).click()
        wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/nav/ul/li[10]/a"))).click()
        wait.until(EC.presence_of_element_located((By.XPATH, '//div[@role="row" and @row-index="0"]')))
        
        ventana_principal = driver.current_window_handle
        wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="ag-myGrid-btnExportarListadoPedidos"]'))).click()
        
        csv_pedidos_realizados = esperar_descarga_completa(download_dir)
        WebDriverWait(driver, 30).until(lambda d: d.execute_script("return document.readyState") == "complete")

        # Descargar segundo archivo
        logger.info("Descargando pedidos realizados pre...")
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="navToggle"]'))).click()
        wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/nav/ul/li[11]/a"))).click()
        wait.until(EC.presence_of_element_located((By.XPATH, '//div[@role="row" and @row-index="0"]')))
        
        wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="ag-myGrid-btnExportarListadoPedidos"]'))).click()
        csv_pedidos_realizados_pre = esperar_descarga_completa(download_dir, archivo_previo=csv_pedidos_realizados)

        return {
            'pedidos_realizados': csv_pedidos_realizados,
            'pedidos_realizados_pre': csv_pedidos_realizados_pre
        }

    except Exception as e:
        logger.error(f"Error en proceso Selenium: {str(e)}")
        screenshot_path = os.path.join(download_dir, f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        driver.save_screenshot(screenshot_path)
        logger.info(f"Screenshot guardado en: {screenshot_path}")
        raise
    finally:
        driver.quit()
        logger.info("Navegador cerrado")

def consolidar_archivos_descargados(archivos_descargados, download_dir):
    """
    Consolida los archivos descargados en un solo CSV.

    Args:
        archivos_descargados (list or dict): Lista o dict con rutas de los archivos CSV a consolidar.
        download_dir (str): Directorio donde se guardará el archivo consolidado.

    Returns:
        str: Ruta del archivo consolidado.
    """
    if isinstance(archivos_descargados, dict):
        archivos = list(archivos_descargados.values())
    else:
        archivos = archivos_descargados

    df_list = []
    for archivo in archivos:
        try:
            df = pd.read_csv(archivo,sep=";",quotechar='"')
            df_list.append(df)
            logger.info(f"Archivo agregado a consolidación: {archivo}")
        except Exception as e:
            logger.error(f"Error leyendo {archivo}: {e}")

    if not df_list:
        raise ValueError("No se pudieron leer archivos para consolidar.")

    df_final = pd.concat(df_list, ignore_index=True)

    # Generar nombre con timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(download_dir, f"consolidado_{timestamp}.csv")

    df_final.to_csv(output_path, index=False)
    logger.info(f" Consolidado guardado en: {output_path}")
    return output_path


def obtener_token_ropc():
    token_url = f"https://login.microsoftonline.com/{os.getenv('TENANT_ID_MICROSOFT')}/oauth2/v2.0/token"
    data = {
        "grant_type": "password",
        "client_id": os.getenv('CLIENT_ID_AZURE'),
        "client_secret": os.getenv('CLIENT_SECRET_AZURE'),
        "username": os.getenv('USUARIO_MICROSOFT'),
        "password": os.getenv('CONTRASENA_MICROSOFT'),
        "scope": "https://graph.microsoft.com/.default"
    }
    resp = requests.post(token_url, data=data)
    resp.raise_for_status()
    access_token = resp.json().get("access_token")
    if not access_token:
        raise Exception("No se pudo obtener access_token desde Azure AD")
    return {"Authorization": f"Bearer {access_token}"}

def obtener_site_y_drive_id(headers, site_url, drive_name="Documentos"):
    from urllib.parse import urlparse
    parsed = urlparse(site_url)
    host = parsed.netloc
    path = parsed.path.strip("/")
    resp_site = requests.get(f"https://graph.microsoft.com/v1.0/sites/{host}:/{path}", headers=headers)
    resp_site.raise_for_status()
    site_id = resp_site.json()["id"]
    resp_drives = requests.get(f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives", headers=headers)
    resp_drives.raise_for_status()
    drives = resp_drives.json().get("value", [])
    for d in drives:
        if d["name"] == drive_name:
            drive_id = d["id"]
            break
    else:
        raise Exception(f"No se encontró el drive con nombre: {drive_name}")
    return site_id, drive_id

def descargar_archivo_sharepoint_graph(headers, site_id, drive_id, file_path, download_to):
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root:/{file_path}:/content"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    with open(download_to, "wb") as f:
        f.write(resp.content)

def proceso_etl_sharepoint(credenciales, consolidado_path):
    try:
        logger.info("Iniciando proceso ETL SharePoint")
        inicio_proceso = datetime.now()

        # ===================== DESCARGA ARCHIVO SHAREPOINT CON GRAPH =====================
        logger.info("Descargando archivo desde SharePoint con Graph API")
        headers = obtener_token_ropc()
        site_id, drive_id = obtener_site_y_drive_id(
            headers, 
            credenciales["SHAREPOINT_SITE_DOCUMENTOS_CLIENTES"], 
            drive_name="Documentos"
        )
        file_path = "Nestle/NESTLE DROGUERIAS/ETL/TRANSFERENCIAS/Parametrizacion.xlsx"
        download_dir = os.path.abspath("descargas_transferencias")
        local_excel_path = os.path.join(download_dir, "Parametrizacion_descargada.xlsx")

        descargar_archivo_sharepoint_graph(headers, site_id, drive_id, file_path, local_excel_path)
        logger.info(f"Archivo descargado desde SharePoint a: {local_excel_path}")

        # ===================== CARGA DE EXCEL =====================
        xls = pd.ExcelFile(local_excel_path)
        logger.info("Archivo Excel cargado en memoria con sheets: %s", xls.sheet_names)

        # ===================== CARGA Y TRANSFORMACIÓN DE TABLAS =====================
        def cargar_y_transformar(sheet_name, subset_cols=None, numeric_cols=None, datetime_cols=None, str_cols=None):
            logger.info("Cargando hoja: %s", sheet_name)
            df = pd.read_excel(xls, sheet_name=sheet_name).dropna(how="all")
            logger.info("Filas después de dropna: %d", len(df))

            # Limpieza de columnas clave
            if subset_cols:
                for col in subset_cols:
                    if df[col].dtype == 'object':
                        df[col] = df[col].str.strip().str.upper()
                
                # Eliminar filas con valores vacíos en las columnas clave
                df = df.dropna(subset=subset_cols)
                for col in subset_cols:
                    if df[col].dtype == 'object':
                        df = df[df[col] != ""]
                
                df = df.drop_duplicates(subset=subset_cols)
                logger.info("Filas después de limpieza y drop_duplicates por %s: %d", subset_cols, len(df))

            # Conversión de columnas numéricas
            if numeric_cols:
                for col in numeric_cols:
                    df[col] = pd.to_numeric(df[col], errors='coerce').astype("Int64")
                    logger.info("Columna %s convertida a Int64", col)

            # Conversión de columnas datetime - FORMATO ESPECÍFICO PARA SQL
            if datetime_cols:
                for col in datetime_cols:
                    # Convertir a datetime y luego a date (sin hora)
                    df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
                    logger.info("Columna %s convertida a date (sin hora)", col)

            # Conversión de columnas a string explícitamente
            if str_cols:
                for col in str_cols:
                    # Convertir a string, manejando nulos explícitamente
                    df[col] = df[col].astype(str).replace('nan', None).replace('None', None)
                    logger.info("Columna %s convertida a str", col)

            return df


        df_tb_homologacion_zona_regional = cargar_y_transformar("HomologacionRegional", subset_cols=["TRANSFERENCISTA"])
        df_tb_homologacion_parrilla = cargar_y_transformar("HomologacionParrilla", subset_cols=["DESCRIPCION"])
        
        df_tb_homologacion_fe_panel = cargar_y_transformar("FePanel", subset_cols=["MES","CODIGO PDV"], numeric_cols=["CODIGO PDV"], datetime_cols=["MES"], str_cols=["VENDEDOR", "DIRECCION","COD COPIDROGAS"])
        
        df_tb_homologacion_fe_Kilos = cargar_y_transformar("FeHomologacionKilos", subset_cols=["ID"], numeric_cols=["ID"],str_cols=["Producto","Gr o ML"])
        df_tb_homologacion_fe_maestra_productos = cargar_y_transformar("FeMaestraProductos", subset_cols=["Material"], numeric_cols=["Material"])
        df_tb_homologacion_fe_Infaltables = cargar_y_transformar("FeInfaltables", subset_cols=["Material","TIPO PDV"], numeric_cols=["Material"])
        
        df_tb_homologacion_fe_cuota_producto_foco = cargar_y_transformar("FeCuotaProductoFoco", subset_cols=["AÑO","MES","VUM","PRODUCTO"])
        df_tb_homologacion_fe_cuota_producto_foco["AÑO"] = pd.to_numeric(df_tb_homologacion_fe_cuota_producto_foco["AÑO"], errors="coerce").astype("Int64")
        df_tb_homologacion_fe_cuota_producto_foco["MES"] = pd.to_numeric(df_tb_homologacion_fe_cuota_producto_foco["MES"], errors="coerce").astype("Int64")
        df_tb_homologacion_fe_cuota_producto_foco["CUOTA"] = pd.to_numeric(df_tb_homologacion_fe_cuota_producto_foco["CUOTA"], errors="coerce")

        df_tb_homologacion_fe_cuota_usuarios = cargar_y_transformar("FeCuotaUsuarios", subset_cols=["AÑO","MES","VUM"],numeric_cols=["AÑO", "MES"])

        # Lista explícita de columnas esperadas
        cuota_cols = [
            "CUOTA FORMULAS INFANTILES",
            "CUOTA GUMS",
            "TOTAL",
            "CUOTA IMPACTOS",
            "CUOTA PODUCTO FOCO NESTOGENO1 X 400 GR",
            "CUOTAPODUCTO FOCO NESTOGENO2 X 800 GR",
            "CUOTA UNIDADES NUTREN",
            "CUOTA KILOS NUTREN"
        ]
        # Procesar solo si existen en el DataFrame
        for col in cuota_cols:
            if col in df_tb_homologacion_fe_cuota_usuarios.columns:
                df_tb_homologacion_fe_cuota_usuarios[col] = (
                    pd.to_numeric(df_tb_homologacion_fe_cuota_usuarios[col], errors="coerce")
                )
                logger.info("Columna %s convertida a numérica", col)
            else:
                logger.warning("Columna %s no encontrada en el DataFrame", col)


        # ===================== TRANSFERENCIAS =====================
        logger.info("Cargando archivo consolidado: %s", consolidado_path)
        df_consolidado_ventas = pd.read_csv(consolidado_path)
        logger.info("Archivo consolidado cargado con %d registros", len(df_consolidado_ventas))

        # Renombrar columnas y transformar
        cols = {
            'Estado': 'Estado', 'N Pedido Cliente': 'NPedidoCliente', 'Fecha Pedido Cliente': 'FechaPedidoCliente',
            'N Transferencia': 'NTransferencia', 'N Posicion': 'NPosicion', 'Tipo de Pedido': 'TipodePedido',
            'Codigo Drogueria': 'CodigoDrogueria', 'Drogueria': 'Drogueria', 'Ciudad': 'Ciudad', 'Centro': 'Centro',
            'Clase de Transferencia': 'ClasedeTransferencia', 'Evento': 'Evento', 'Fecha Transferencia': 'FechaTransferencia',
            'Material': 'Material', 'Descripcion': 'Descripcion', 'Lote': 'Lote', 'Cantidad': 'Cantidad',
            'Bonificacion': 'Bonificacion', 'Precio': 'Precio', 'Impuesto': 'Impuesto',
            'Total con Iva': 'TotalconIva', 'Total sin Iva': 'TotalsinIva', 'Transferencista': 'Transferencista', 'Proveedor': 'Proveedor'
        }

        df_consolidado_ventas = df_consolidado_ventas[list(cols.keys())].rename(columns=cols)
        logger.info("Columnas renombradas y seleccionadas")

        # Fecha a Timestamp (sin hora)
        df_consolidado_ventas["FechaTransferencia"] = pd.to_datetime(df_consolidado_ventas["FechaTransferencia"]).dt.normalize()

        hoy = pd.Timestamp.today().normalize()
        inicio_mes_actual = hoy.replace(day=1)

        if hoy.day <= 5:
            inicio_mes_anterior = (inicio_mes_actual - pd.DateOffset(months=1)).replace(day=1)
            filtro = (df_consolidado_ventas["FechaTransferencia"] >= inicio_mes_anterior) & \
                    (df_consolidado_ventas["FechaTransferencia"] <= hoy)
            logger.info("Filtrando datos desde %s hasta %s", inicio_mes_anterior.date(), hoy.date())
        else:
            filtro = (df_consolidado_ventas["FechaTransferencia"] >= inicio_mes_actual) & \
                    (df_consolidado_ventas["FechaTransferencia"] <= hoy)
            logger.info("Filtrando datos desde %s hasta %s", inicio_mes_actual.date(), hoy.date())

        df_consolidado_ventas = df_consolidado_ventas[filtro]
        logger.info("Filas después del filtro: %d", len(df_consolidado_ventas))



        # Limpiezas
        df_consolidado_ventas["Estado"] = df_consolidado_ventas["Estado"].str.lstrip()
        df_consolidado_ventas["Material"] = pd.to_numeric(df_consolidado_ventas["Material"], errors="coerce").astype("Int64")
        
        for col in ["Precio", "TotalconIva", "TotalsinIva"]:
            df_consolidado_ventas[col] = (
                df_consolidado_ventas[col]
                .astype(str)
                .str.replace(r"[^0-9]", "", regex=True)
                .astype("Int64")
            )
            logger.info("Columna %s limpiada y convertida a Int64", col)

        df_consolidado_ventas["Impuesto"] = pd.to_numeric(df_consolidado_ventas["Impuesto"], errors="coerce").round(2)

        fin_proceso = datetime.now()
        logger.info("Proceso ETL SharePoint completado en %s segundos", (fin_proceso - inicio_proceso).total_seconds())

        return {
            "df_zona_regional": df_tb_homologacion_zona_regional,
            "df_parrilla": df_tb_homologacion_parrilla,
            "df_panel": df_tb_homologacion_fe_panel,
            "df_kilos": df_tb_homologacion_fe_Kilos,
            "df_maestra_productos": df_tb_homologacion_fe_maestra_productos,
            "df_infaltables": df_tb_homologacion_fe_Infaltables,
            "df_cuota_producto_foco": df_tb_homologacion_fe_cuota_producto_foco,
            "df_cuota_usuarios": df_tb_homologacion_fe_cuota_usuarios,
            "df_consolidado_ventas": df_consolidado_ventas
        }

    except Exception as e:
        logger.error("Error en el proceso ETL SharePoint: %s", str(e), exc_info=True)
        raise

def cargar_dataframes_sqlserver_con_llave(
    credenciales, 
    dataframes_config, 
    esquema="dbo", 
    driver="ODBC Driver 17 for SQL Server",
    nombre_proceso="ETL_TRANSFERENCIAS_NESTLE_DROGUERIAS", 
    fuente="SharePoint",
    mostrar_errores_completos=False
):
    """
    Carga múltiples DataFrames a SQL Server con:
    - Inserción a tabla temporal
    - DELETE con INNER JOIN tabla real vs temporal
    - Inserción final a tabla real
    - Logging y estado por tabla
    """
    try:
        logger.info(f"Conectando a SQL Server: {credenciales['SERVER_SQL_15']}")

        conn_str = (
            f"DRIVER={driver};"
            f"SERVER={credenciales['SERVER_SQL_15']};"
            f"DATABASE={credenciales['DATABASE_U_D_NESTLE_DROGUERIAS']};"
            f"UID={credenciales['USER_SQL']};"
            f"PWD={credenciales['PASSWORD_SQL']};"
            "autocommit=True;Connection Timeout=60;"
            "Encrypt=yes;"
            "TrustServerCertificate=yes;"
        )

        params = urllib.parse.quote_plus(conn_str)

        engine = sqlalchemy.create_engine(
            f"mssql+pyodbc:///?odbc_connect={params}",
            fast_executemany=False,
            pool_pre_ping=True,
            connect_args={'timeout': 60}
        )

        for config in dataframes_config:
            start_time = time.time()
            tabla_sql = f"{esquema}.{config['tabla_sql']}"
            df = config["dataframe"].copy()
            llave = config["llave"]
            column_mapping = config.get("column_mapping", {})

            logger.info(f"Procesando tabla {tabla_sql}: {df.shape[0]} filas")

            try:
                if column_mapping:
                    df = df.rename(columns=column_mapping)

                df = df.replace({np.nan: None, pd.NA: None})

                temp_table_name = f"##TMP_{config['tabla_sql']}"

                with engine.begin() as conn:
                    # 1️⃣ Crear tabla temporal
                    columnas_sql = ", ".join([f"[{col}] NVARCHAR(MAX)" for col in df.columns])
                    conn.execute(text(f"IF OBJECT_ID('tempdb..{temp_table_name}') IS NOT NULL DROP TABLE {temp_table_name}"))
                    #conn.execute(text(f"CREATE TABLE {temp_table_name} ({columnas_sql})"))
                    logger.info(f"Tabla temporal {temp_table_name} creada")

                    # 2️⃣ Insertar en tabla temporal
                    df.to_sql(
                        name=temp_table_name,
                        con=conn,
                        schema=None,
                        if_exists="append",
                        index=False,
                        chunksize=500,
                        method=None
                    )
                    logger.info(f"Datos insertados en {temp_table_name}")

                    # 3️⃣ Eliminar en tabla real con JOIN
                    if llave:
                        join_conds = " AND ".join([f"real.[{col}] = tmp.[{col}]" for col in llave])
                        delete_sql = f"""
                        DELETE real
                        FROM {tabla_sql} AS real
                        INNER JOIN {temp_table_name} AS tmp
                        ON {join_conds}
                        """
                        conn.execute(text(delete_sql))
                        logger.info(f"Registros eliminados en {tabla_sql} con JOIN a {temp_table_name}")

                    # 4️⃣ Insertar en tabla real desde temporal
                    cols_list = ", ".join([f"[{col}]" for col in df.columns])
                    insert_sql = f"""
                    INSERT INTO {tabla_sql} ({cols_list})
                    SELECT {cols_list} FROM {temp_table_name}
                    """
                    conn.execute(text(insert_sql))
                    logger.info(f"Datos insertados en {tabla_sql} desde {temp_table_name}")

                    # 5️⃣ Limpiar temporal
                    conn.execute(text(f"DROP TABLE {temp_table_name}"))

                    # 6️⃣ Registro de éxito
                    conn.execute(text(f"""
                        INSERT INTO Utiles_NESTLE_DROGUERIAS.{esquema}.tbEstadoETLS 
                        (NombreProceso, NombreTabla, Fuente, Resultado, DetalleError,Fecha)
                        VALUES (:proceso, :tabla, :fuente, 'Éxito', '',GETDATE())
                    """), {
                        'proceso': nombre_proceso,
                        'tabla': config["tabla_sql"],
                        'fuente': fuente
                    })

                    logger.info(f"Tabla {tabla_sql} cargada en {time.time() - start_time:.2f}s")

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error en {tabla_sql}: {error_msg}", exc_info=mostrar_errores_completos)
                with engine.begin() as conn:
                    conn.execute(text(f"""
                        INSERT INTO Utiles_NESTLE_DROGUERIAS.{esquema}.tbEstadoETLS 
                        (NombreProceso, NombreTabla, Fuente, Resultado, DetalleError,Fecha)
                        VALUES (:proceso, :tabla, :fuente, 'Error', :error,GETDATE())
                    """), {
                        'proceso': nombre_proceso,
                        'tabla': config["tabla_sql"],
                        'fuente': fuente,
                        'error': error_msg[:500]
                    })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error general en carga de DataFrames: {error_msg}")
        if mostrar_errores_completos:
            raise
    
    # 🚀 Ejecución del SP al final
    logger.info("Ejecutando SP: spCargaNestleDrogueriasTransferencias")
    with engine.begin() as conn:
        conn.execute(text("EXEC spCargaNestleDrogueriasTransferencias"))
    logger.info("SP ejecutado correctamente")

def main():
    """Función principal que orquesta todo el proceso"""
    try:
        logger.info("Iniciando ETL de transferencias")
        
        # Configuración inicial
        env_paths = [r'C:\Scripts\config.env']
        credenciales = configurar_entorno(env_paths=env_paths)
        download_dir = os.path.abspath("descargas_transferencias")
        
        # Ejecutar proceso Selenium
        archivos_descargados = proceso_selenium(download_dir, credenciales)
        
        # Aquí puedes agregar el procesamiento de los archivos descargados
        logger.info(f"Archivos descargados: {archivos_descargados}")
        
        # Consolidar
        consolidado_path = consolidar_archivos_descargados(archivos_descargados,download_dir)
        
        # Limpieza de descargas
        limpiar_descargas(download_dir,excluir=[os.path.basename(consolidado_path)])
        ##consolidado_path = r"C:\Users\jhon.piza\Docs jhon.piza\OneDrive - Vision & Marketing S.A.S\Documentos\Personal\ETL\NESTLE DROGUERIAS\descargas\DATOS_HISTORICO_TRANSFERENCIAS_COMA.csv"

        dfs = proceso_etl_sharepoint(credenciales,consolidado_path)
        logger.info("Proceso completado exitosamente")

        dataframes_config = [
                            {
                                "tabla_sql": "tbNestleDrogueriasTransferenciasZonaRegional", 
                                "dataframe": dfs["df_zona_regional"], 
                                "llave": ["Transferencista"],
                                "column_mapping": {
                                    "TRANSFERENCISTA" : "Transferencista",
                                    "ZONA" : "Zona",
                                    "REGIONAL" : "Regional",
                                    "ZONA2" : "ZonaII",
                                }
                            },
                            {
                                "tabla_sql": "tbNestleDrogueriasTransferenciasParilla",
                                "dataframe": dfs["df_parrilla"],
                                "llave": ["Descripcion"],
                                "column_mapping": {
                                    "DESCRIPCION" : "Descripcion",
                                    "CATEGORIA" : "Categoria",
                                    "SUBCATEGORIA" : "Subcategoria",
                                }
                            },
                            {
                                "tabla_sql": "tbNestleDrogueriasTransferenciasPanel",
                                "dataframe": dfs["df_panel"],
                                "llave": ["Mes", "CodigoPdv"],
                                "column_mapping": {
                                    "REGIONAL" : "Regional",
                                    "CADENA" : "Cadena",
                                    "SUBCADENA" : "Subcadena",
                                    "CODIGO PDV" : "CodigoPdv",
                                    "NOMBRE COMERCIAL" : "NombreComercial",
                                    "TIPO PUNTO VENTA" : "TipoPuntoVenta",
                                    "VENDEDOR" : "Vendedor",
                                    "COD COPIDROGAS" : "CodCopidrogas",
                                    "DIRECCION" : "Direccion",
                                    "USUARIO" : "Usuario",
                                    "MES" : "Mes",
                                }
                            },
                            {
                                "tabla_sql": "tbNestleDrogueriasTransferenciasKilos",
                                "dataframe": dfs["df_kilos"],
                                "llave": ["Id"],
                                "column_mapping": {
                                    "ID" : "Id",
                                    "Producto" : "Producto",
                                    "Gr o ML" : "GroMl",
                                }
                            },
                            {
                                "tabla_sql": "tbNestleDrogueriasTransferenciasMaestraProductos",
                                "dataframe": dfs["df_maestra_productos"],
                                "llave": ["Material"],
                                "column_mapping": {
                                    "Material" : "Material",
                                    "Descripcion" : "Descripcion",
                                    "CATEGORIA" : "Categoria",
                                    "INFALTABLES" : "Infaltables",
                                    "SUBCATEGORIA" : "Subcategoria",
                                    "SUCATEGORIA ESPECIFICA" : "SucategoriaEspecifica",
                                }
                            },
                            {
                                "tabla_sql": "tbNestleDrogueriasTransferenciasInfaltables",
                                "dataframe": dfs["df_infaltables"],
                                "llave": ["Material", "TipoPdv"],
                                "column_mapping": {
                                    "TIPO PDV" : "TipoPdv",
                                    "Descripcion" : "Descripcion",
                                    "Material" : "Material",
                                    "Infaltable" : "Infaltable",
                                    "Categoria" : "Categoria",
                                }
                            },
                            {
                                "tabla_sql": "tbNestleDrogueriasTransferenciasCuotaProductoFoco",
                                "dataframe": dfs["df_cuota_producto_foco"],
                                "llave": ["Año", "Mes", "Vum", "Producto"],
                                "column_mapping": {
                                    "AÑO" : "Año",
                                    "MES" : "Mes",
                                    "REGIONAL " : "Regional",
                                    "VUM" : "Vum",
                                    "TRANSFERENCISTA" : "Transferencista",
                                    "PRODUCTO" : "Producto",
                                    "CUOTA" : "Cuota",
                                }
                            },
                            {
                                "tabla_sql": "tbNestleDrogueriasTransferenciasCuotaUsuarios",
                                "dataframe": dfs["df_cuota_usuarios"],
                                "llave": ["Año", "Mes", "Vum"],
                                "column_mapping": {
                                    "AÑO" : "Año",
                                    "MES" : "Mes",
                                    "REGIONAL " : "Regional",
                                    "VUM" : "Vum",
                                    "CUOTA FORMULAS INFANTILES" : "CuotaFormulasInfantiles",
                                    "CUOTA GUMS" : "CuotaGums",
                                    "TOTAL" : "Total",
                                    "CUOTA IMPACTOS" : "CuotaImpactos",
                                    "CUOTA PODUCTO FOCO NESTOGENO1 X 400 GR" : "CuotaPoductoFocoNestogenoIxCDGr",
                                    "CUOTAPODUCTO FOCO NESTOGENO2 X 800 GR" : "CuotapoductoFocoNestogenoIIxDCCCGr",
                                    "CUOTA UNIDADES NUTREN" : "CuotaUnidadesNutren",
                                    "CUOTA KILOS NUTREN" : "CuotaKilosNutren",
                                }
                            },
                            {
                                "tabla_sql": "tbNestleDrogueriasTransferenciasCrudo",
                                "dataframe": dfs["df_consolidado_ventas"],
                                "llave": ["Fechatransferencia"],
                                "column_mapping": {
                                    "Estado" : "Estado",
                                    "NPedidoCliente" : "Npedidocliente",
                                    "FechaPedidoCliente" : "Fechapedidocliente",
                                    "NTransferencia" : "Ntransferencia",
                                    "NPosicion" : "Nposicion",
                                    "TipodePedido" : "Tipodepedido",
                                    "CodigoDrogueria" : "Codigodrogueria",
                                    "Drogueria" : "Drogueria",
                                    "Ciudad" : "Ciudad",
                                    "Centro" : "Centro",
                                    "ClasedeTransferencia" : "Clasedetransferencia",
                                    "Evento" : "Evento",
                                    "FechaTransferencia" : "Fechatransferencia",
                                    "Material" : "Material",
                                    "Descripcion" : "Descripcion",
                                    "Lote" : "Lote",
                                    "Cantidad" : "Cantidad",
                                    "Bonificacion" : "Bonificacion",
                                    "Precio" : "Precio",
                                    "Impuesto" : "Impuesto",
                                    "TotalconIva" : "Totalconiva",
                                    "TotalsinIva" : "Totalsiniva",
                                    "Transferencista" : "Transferencista",
                                    "Proveedor" : "Proveedor",
                                }
                            }
                        ]
        
        cargar_dataframes_sqlserver_con_llave(
            credenciales, 
            dataframes_config, 
            esquema="dbo", 
            nombre_proceso="ETL_TRANSFERENCIAS_NESTLE_DROGUERIAS", 
            fuente="SharePoint"
        )

        limpiar_descargas(download_dir)
    except Exception as e:
        logger.error(f"Error en el proceso principal: {str(e)}")
        raise

if __name__ == "__main__":
    main()

        