import os
import sys
import re
import shutil
import requests
from pathlib import Path
from subprocess import run, CalledProcessError
import json
import time

# --- CONFIGURACIÓN GLOBAL ---

# URL base del repositorio y nombre de la rama (ajustar si es necesario)
REPO_OWNER = "JhonPizaVision"
REPO_NAME = "VisionyMarketing"
REPO_BRANCH = "main"
REPO_SCRIPTS_FOLDER = "Scripts"

# URL base para la API de contenido de GitHub
GITHUB_API_BASE = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents"

BASE_DIR = Path("C:/Scripts") # Ruta base explícita solicitada por el usuario
CONFIG_ENV_PATH = BASE_DIR / "config.env"
LOCAL_VERSION_FILE = ".local_version.txt"

# --- DETECCIÓN DE EJECUCIÓN DESDE EXE ---
def is_running_from_exe():
    """Detecta si el script se está ejecutando desde un archivo .exe"""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

# --- FUNCIONES DE UTILIDAD ---

def clear_console(step_name):
    """Borra la consola para una presentación más limpia y profesional."""
    print(f"\n{'=' * 50}\n-> {step_name}\n{'=' * 50}")

def exponential_backoff_fetch(url, max_retries=5, initial_delay=1):
    """Realiza una solicitud GET con reintentos y backoff exponencial."""
    headers = {"Accept": "application/vnd.github.com.v3.raw"}
    delay = initial_delay
    
    for attempt in range(max_retries):
        try:
            # Usar un header de No Cache para obtener la versión más reciente
            headers["Cache-Control"] = "no-cache"
            response = requests.get(url, headers=headers)
            response.raise_for_status() # Lanza una excepción para errores 4xx/5xx
            return response
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise e
            print(f"Error en la solicitud (Intento {attempt + 1}/{max_retries}). Reintentando en {delay}s...")
            time.sleep(delay)
            delay *= 2
    return None

def ensure_base_directories():
    """Asegura que la carpeta base C:\\Scripts exista."""
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Directorio base asegurado: {BASE_DIR}")

def get_user_input():
    """Solicita al usuario el CLIENTE y PROYECTO."""
    clear_console("SOLICITUD DE DATOS")
    print("Directorio base: C:\\Scripts")
    print("-" * 50)
    client = input("Ingrese el nombre del CLIENTE (ej: ABBOTT): ").strip()
    project = input("Ingrese el nombre del PROYECTO (ej: ABBOTT_ELT_VENTAS): ").strip()

    if not client or not project:
        print("El CLIENTE y PROYECTO son obligatorios. Saliendo.")
        sys.exit(1)

    return client, project

def download_project_files(client, project, project_dir, target_api_path=None):
    """Descarga los archivos del proyecto usando la API de GitHub."""
    
    api_path = target_api_path if target_api_path else f"{REPO_SCRIPTS_FOLDER}/{client}/{project}"
    api_url = f"{GITHUB_API_BASE}/{api_path}?ref={REPO_BRANCH}"
    
    try:
        response = exponential_backoff_fetch(api_url)
        content_list = response.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: No se pudo acceder a la API de GitHub para la ruta {api_path}. {e}")
        if 'response' in locals() and response.status_code == 404:
            print(f"ERROR: El proyecto no existe o la ruta no es correcta en el repositorio: {api_path}")
        return False, []
    except json.JSONDecodeError:
        print(f"ERROR: Respuesta de API inválida (no JSON).")
        return False, []
        
    if not isinstance(content_list, list):
         print(f"ERROR: La ruta {api_path} no parece ser un directorio o está vacía.")
         return False, []
        
    project_dir.mkdir(parents=True, exist_ok=True)
    
    found_files = 0
    downloaded_files = []
    
    for item in content_list:
        if item.get("type") == "file":
            file_name = item["name"]
            download_url = item["download_url"]
            target_path = project_dir / file_name
            
            try:
                file_response = exponential_backoff_fetch(download_url)
                
                with open(target_path, 'wb') as f:
                    f.write(file_response.content)
                
                downloaded_files.append(file_name)
                found_files += 1
                
            except requests.exceptions.RequestException as e:
                print(f"ERROR: No se pudo descargar el archivo {file_name}. {e}")
                
    if found_files == 0:
        print(f"ERROR: No se encontraron archivos descargables en la ruta {api_path}.")
        return False, []

    return True, downloaded_files

def check_env_variables(project_dir, project_name):
    """Comprueba y pide variables de entorno faltantes en config.env."""
    clear_console("PASO 2: Verificando variables de entorno")

    env_requirements_path = project_dir / f"{project_name}_ENV.txt"
    if not env_requirements_path.exists():
        print(f"ADVERTENCIA: No se encontró el archivo de requisitos de ENV: {env_requirements_path}")
        return

    required_vars = set()
    try:
        with open(env_requirements_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    required_vars.add(line.split('=')[0]) 
    except Exception as e:
        print(f"ERROR: No se pudo leer el archivo de requisitos de ENV. {e}")
        return

    if not required_vars:
        print("No hay variables de entorno requeridas en el archivo _ENV.txt.")
        return

    existing_vars = {}
    if CONFIG_ENV_PATH.exists():
        try:
            with open(CONFIG_ENV_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    match = re.match(r'^(\w+)=(.*)$', line.strip())
                    if match:
                        key, value = match.groups()
                        existing_vars[key] = value
        except Exception as e:
            print(f"ADVERTENCIA: No se pudo leer config.env. Se continuará. {e}")

    missing_vars = required_vars - set(existing_vars.keys())

    if missing_vars:
        print(f"Faltan las siguientes variables en {CONFIG_ENV_PATH}: {', '.join(missing_vars)}")
        
        try:
            with open(CONFIG_ENV_PATH, 'a', encoding='utf-8') as f:
                f.write(f"\n# --- Variables añadidas para el proyecto: {project_name} ---\n")
                for var in sorted(list(missing_vars)):
                    value = input(f"Ingrese el valor para la variable '{var}': ").strip()
                    f.write(f"{var}={value}\n")
                    print(f"'{var}' añadido a config.env")
        except Exception as e:
            print(f"ERROR: No se pudo escribir en config.env. Revise permisos. {e}")
    else:
        print("Todas las variables de entorno requeridas ya están presentes.")

def setup_virtual_environment(project_dir, project_name):
    """Crea el venv e instala las dependencias."""
    clear_console("PASO 3: Configurando Entorno Virtual (VENV) y dependencias")
    venv_dir = project_dir / "venv"
    requirements_path = project_dir / f"{project_name}_REQUERIMENTS.txt"
    
    if not venv_dir.exists():
        print("Creando nuevo VENV...")
        try:
            # DETECCIÓN CRÍTICA: Si estamos en un EXE, usar python.exe del sistema
            if is_running_from_exe():
                # Buscar Python en el sistema
                python_path = shutil.which("python") or shutil.which("python.exe")
                if python_path:
                    run([python_path, "-m", "venv", str(venv_dir)], check=True, stdout=sys.stdout, stderr=sys.stderr)
                    print("VENV creado exitosamente usando Python del sistema.")
                else:
                    print("ERROR: No se encontró Python en el sistema PATH.")
                    print("Por favor, instale Python o ejecute project_deployer.py directamente.")
                    return None
            else:
                # Ejecución normal desde Python
                run([sys.executable, "-m", "venv", str(venv_dir)], check=True, stdout=sys.stdout, stderr=sys.stderr)
                print("VENV creado exitosamente.")
        except CalledProcessError as e:
            print(f"ERROR: No se pudo crear el VENV. {e}")
            return None
    else:
        print("VENV ya existe.")

    if requirements_path.exists():
        if sys.platform == "win32":
            pip_executable = venv_dir / "Scripts" / "pip.exe"
        else:
            pip_executable = venv_dir / "bin" / "pip"

        if not pip_executable.exists():
            print(f"ADVERTENCIA: No se encontró el ejecutable de pip en VENV.")
            return venv_dir

        print("Instalando/actualizando dependencias. Esto puede tomar un momento...")
        try:
            run([str(pip_executable), "install", "-r", str(requirements_path), "--upgrade"], 
                check=True, stdout=sys.stdout, stderr=sys.stderr)
            print("Dependencias instaladas exitosamente.")
            return venv_dir
        except CalledProcessError as e:
            print(f"ERROR: No se pudieron instalar las dependencias. {e}")
            return None
    else:
        print(f"ADVERTENCIA: No se encontró el archivo de requisitos: {requirements_path}")
        return venv_dir

# Nuevo: Contenido del script de ejecución, actualización y validación
def generate_executor_script(client, project, project_dir):
    """Genera el contenido del script de ejecución con la lógica de versión y actualización."""
    
    # NOTA: Este script no necesita PyInstaller, ya que PyInstaller será instalado
    # en el entorno principal de project_deployer.py para compilar este script.
    
    script_content = f"""
import os
import sys
import re
import requests
import json
import time
from pathlib import Path
from subprocess import run, CalledProcessError

# --- CONFIGURACIÓN DE EJECUCIÓN ---
CLIENT = "{client}"
PROJECT = "{project}"
REPO_OWNER = "{REPO_OWNER}"
REPO_NAME = "{REPO_NAME}"
REPO_BRANCH = "{REPO_BRANCH}"
REPO_SCRIPTS_FOLDER = "{REPO_SCRIPTS_FOLDER}"
GITHUB_API_BASE = f"https://api.github.com/repos/{{REPO_OWNER}}/{{REPO_NAME}}/contents"

BASE_DIR = Path("C:/Scripts") 
CONFIG_ENV_PATH = BASE_DIR / "config.env"
PROJECT_DIR = BASE_DIR / CLIENT / PROJECT
LOCAL_VERSION_FILE = ".local_version.txt"

# --- FUNCIONES DE UTILIDAD (Clonadas del deployer) ---

def clear_console(step_name):
    print(f"\\n{{'=' * 70}}\\n-> {{step_name}}\\n{{'=' * 70}}")

def exponential_backoff_fetch(url, max_retries=5, initial_delay=1):
    headers = {{"Accept": "application/vnd.github.com.v3.raw", "Cache-Control": "no-cache"}}
    delay = initial_delay
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status() 
            return response
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise e
            print(f"ADVERTENCIA: Error en la solicitud de API. Reintentando...")
            time.sleep(delay)
            delay *= 2
    return None

def download_project_files(project_dir, api_url):
    try:
        response = exponential_backoff_fetch(api_url)
        content_list = response.json()
    except Exception as e:
        print(f"ERROR: No se pudo obtener la lista de archivos del proyecto. {{e}}")
        return False
        
    if not isinstance(content_list, list):
         print(f"ERROR: La respuesta de la API no es un directorio válido.")
         return False
        
    project_dir.mkdir(parents=True, exist_ok=True)
    
    found_files = 0
    print(f"Archivos encontrados ({{len(content_list)}}). Descargando y sobrescribiendo...")
    
    for item in content_list:
        if item.get("type") == "file":
            file_name = item["name"]
            download_url = item["download_url"]
            target_path = project_dir / file_name
            
            try:
                file_response = exponential_backoff_fetch(download_url)
                
                with open(target_path, 'wb') as f:
                    f.write(file_response.content)
                
                print(f"  - Descargado: {{file_name}}")
                found_files += 1
                
            except requests.exceptions.RequestException as e:
                print(f"ERROR: No se pudo descargar el archivo {{file_name}}. {{e}}")
                
    if found_files == 0:
        print(f"ERROR: No se encontraron archivos descargables.")
        return False

    print(f"Actualización completada ({{found_files}} archivos).")
    return True

def check_env_variables_after_update(project_dir, project_name):
    #Comprueba y pide variables de entorno faltantes después de una actualización.
    print("\\nVerificando variables de entorno después de la actualización...")
    
    env_requirements_path = project_dir / f"{{project_name}}_ENV.txt"
    if not env_requirements_path.exists():
        print(f"ADVERTENCIA: No se encontró el archivo de requisitos de ENV: {{env_requirements_path}}")
        return True

    required_vars = set()
    try:
        with open(env_requirements_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    required_vars.add(line.split('=')[0]) 
    except Exception as e:
        print(f"ERROR: No se pudo leer el archivo de requisitos de ENV. {{e}}")
        return False

    if not required_vars:
        print("No hay variables de entorno requeridas en el archivo _ENV.txt.")
        return True

    existing_vars = {{}}
    if CONFIG_ENV_PATH.exists():
        try:
            with open(CONFIG_ENV_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    match = re.match(r'^(\\w+)=(.*)$', line.strip())
                    if match:
                        key, value = match.groups()
                        existing_vars[key] = value
        except Exception as e:
            print(f"ADVERTENCIA: No se pudo leer config.env. {{e}}")
            return False

    missing_vars = required_vars - set(existing_vars.keys())

    if missing_vars:
        print(f"\\nFaltan las siguientes variables en {{CONFIG_ENV_PATH}}: {{', '.join(missing_vars)}}")
        print("Por favor, ingrese los valores para continuar:")
        
        try:
            with open(CONFIG_ENV_PATH, 'a', encoding='utf-8') as f:
                f.write(f"\\n# --- Variables añadidas para el proyecto: {{project_name}} (actualización) ---\\n")
                for var in sorted(list(missing_vars)):
                    value = input(f"Ingrese el valor para la variable '{{var}}': ").strip()
                    f.write(f"{{var}}={{value}}\\n")
                    print(f"  '{{var}}' añadido a config.env")
            return True
        except Exception as e:
            print(f"ERROR: No se pudo escribir en config.env. Revise permisos. {{e}}")
            return False
    else:
        print("Todas las variables de entorno requeridas ya están presentes.")
        return True

def run_project_deployment_steps(project_dir, project_name):
    clear_console("ACTUALIZACIÓN: Configurando VENV y Dependencias")
    
    venv_dir = project_dir / "venv"
    requirements_path = project_dir / f"{{project_name}}_REQUERIMENTS.txt"
    
    # 1. Configurar VENV (solo si falta)
    if not venv_dir.exists():
        # NOTA: En un .exe, sys.executable apunta al .exe, no al Python base.
        # Por simplicidad, asumimos que 'python' está en el PATH o que el VENV ya existe.
        # Si este .exe falla en crear el VENV, el usuario debe re-ejecutar project_deployer.py.
        print("El VENV no existe. Por favor, ejecute project_deployer.py para una configuración inicial completa.")
        return False
    else:
        print("VENV encontrado.")

    # 2. Instalar dependencias
    if requirements_path.exists():
        if sys.platform == "win32":
            pip_executable = venv_dir / "Scripts" / "pip.exe"
        else:
            pip_executable = venv_dir / "bin" / "pip"

        if not pip_executable.exists():
             print(f"ERROR CRÍTICO: No se encontró el ejecutable de pip. El VENV parece roto.")
             return False

        print("Instalando/actualizando dependencias. Esto puede tomar un momento...")
        try:
            # Reinstalamos por si se actualizó el REQUERIMENTS.txt
            run([str(pip_executable), "install", "-r", str(requirements_path), "--upgrade"], 
                check=True, stdout=sys.stdout, stderr=sys.stderr)
            print("Dependencias instaladas exitosamente.")
        except CalledProcessError as e:
            print(f"ERROR: No se pudieron instalar las dependencias. Abortando ejecución. {{e}}")
            return False
    else:
        print(f"ADVERTENCIA: No se encontró el archivo de requisitos: {{requirements_path}}")

    return True

def execute_project_script(project_dir, project_name):
    clear_console("EJECUCIÓN: Iniciando el script principal del proyecto")
    
    script_path = project_dir / f"{{project_name}}.py"
    venv_dir = project_dir / "venv"
    
    if not script_path.exists():
        print(f"ERROR: No se encontró el script principal: {{script_path}}. Abortando.")
        return

    # Determinar el ejecutable de Python dentro del VENV
    if sys.platform == "win32":
        python_executable = venv_dir / "Scripts" / "python.exe"
    else:
        python_executable = venv_dir / "bin" / "python"
        
    if not python_executable.exists():
        print("ERROR: No se encontró el ejecutable de Python en el VENV. Ejecute project_deployer.py.")
        return

    try:
        print(f"-> Ejecutando: {{python_executable}} {{script_path}}")
        print("----------------------------------------------------------------------")
        run([str(python_executable), str(script_path)], cwd=PROJECT_DIR, check=True)
        print("----------------------------------------------------------------------")
        print(f"Script '{{project_name}}.py' finalizado exitosamente.")

    except CalledProcessError as e:
        print(f"ERROR durante la ejecución del script: {{e}}")
    except Exception as e:
        print(f"Ocurrió un error inesperado al ejecutar: {{e}}")


def main():
    '''Lógica principal del script de ejecución diaria.'''
    
    clear_console(f"PROYECTO: {{PROJECT}} - VERIFICACIÓN Y EJECUCIÓN")
    
    # 1. Definir rutas de archivos de versión y API
    remote_version_file_name = f"{{PROJECT}}_VERSION.txt"
    remote_version_api_path = f"{{REPO_SCRIPTS_FOLDER}}/{{CLIENT}}/{{PROJECT}}/{{remote_version_file_name}}"
    remote_version_url = f"{{GITHUB_API_BASE}}/{{remote_version_api_path}}?ref={{REPO_BRANCH}}"
    local_version_path = PROJECT_DIR / LOCAL_VERSION_FILE

    # 2. Obtener Versión Remota
    clear_console("VERIFICACIÓN DE VERSIÓN")
    remote_version = ""
    try:
        # Nota: La URL del archivo de versión apunta al archivo en el repositorio
        response = exponential_backoff_fetch(remote_version_url)
        remote_version = response.text.strip()
    except Exception as e:
        print(f"ERROR: No se pudo obtener la versión remota. Usando la versión local (si existe). {{e}}")
        # Si falla, no actualizamos, pero permitimos la ejecución con la versión local.

    # 3. Obtener Versión Local
    local_version = ""
    if local_version_path.exists():
        try:
            with open(local_version_path, 'r', encoding='utf-8') as f:
                local_version = f.read().strip()
        except:
            pass 

    print(f"Versión Local: {{local_version}}")
    print(f"Versión Remota: {{remote_version}}")

    # 4. Decidir si actualizar o ejecutar
    needs_update = remote_version and (local_version != remote_version)
    
    if needs_update:
        print("\\n¡ACTUALIZACIÓN REQUERIDA!")
        
        # 4a. Descargar nuevos archivos del proyecto
        api_path = f"{{REPO_SCRIPTS_FOLDER}}/{{CLIENT}}/{{PROJECT}}"
        api_url = f"{{GITHUB_API_BASE}}/{{api_path}}?ref={{REPO_BRANCH}}"
        
        # Descargamos los archivos del proyecto (incluido el nuevo _VERSION.txt)
        if not download_project_files(PROJECT_DIR, api_url):
            print("FALLO CRÍTICO: No se pudo actualizar el proyecto. Abortando ejecución.")
            return

        # 4b. Verificar variables de entorno después de la actualización
        if not check_env_variables_after_update(PROJECT_DIR, PROJECT):
            print("FALLO CRÍTICO: No se pudieron configurar las variables de entorno. Abortando ejecución.")
            return

        # 4c. Reconfigurar VENV y dependencias (solo si la descarga fue exitosa)
        # Esto solo lo hacemos si hay una actualización
        if not run_project_deployment_steps(PROJECT_DIR, PROJECT):
            print("FALLO CRÍTICO: No se pudo reconfigurar el entorno. Abortando ejecución.")
            return
            
        # 4d. Guardar la nueva versión localmente
        try:
            with open(local_version_path, 'w', encoding='utf-8') as f:
                f.write(remote_version)
            print(f"Versión local actualizada a {{remote_version}}.")
        except Exception as e:
            print(f"ADVERTENCIA: No se pudo guardar la nueva versión local. {{e}}")

    else:
        print("\\nVersión local actualizada. Ejecutando la versión existente.")


    # 5. Ejecutar el script principal (siempre se ejecuta al final, si no hubo fallos críticos)
    execute_project_script(PROJECT_DIR, PROJECT)
    
if __name__ == "__main__":
    main()
"""
    executor_path = project_dir / f"RUN_{project}.py"
    with open(executor_path, 'w', encoding='utf-8') as f:
        f.write(script_content.strip())
    
    return executor_path

def check_python_available():
    """Verifica si Python está disponible en el sistema y si PyInstaller está instalado."""
    python_path = shutil.which("python") or shutil.which("python.exe") or shutil.which("python3")
    
    if python_path:
        print(f"Python encontrado en el sistema: {python_path}")
        
        # Verificar si PyInstaller está instalado
        try:
            result = run([python_path, "-c", "import PyInstaller; print('PyInstaller OK')"], 
                        capture_output=True, text=True, timeout=10)
            if "PyInstaller OK" in result.stdout:
                print("PyInstaller está instalado en el sistema.")
                return True
            else:
                print("PyInstaller no está instalado en el sistema Python.")
                return False
        except (CalledProcessError, TimeoutError):
            print("No se pudo verificar PyInstaller en el sistema Python.")
            return False
    else:
        print("Python no encontrado en el sistema PATH.")
        return False

def install_required_dependencies():
    """Instala las dependencias necesarias para compilar ejecutables."""
    clear_console("VERIFICANDO DEPENDENCIAS NECESARIAS")
    
    dependencies = ["requests", "pyinstaller", "pillow"]
    missing_deps = []
    
    print("Verificando dependencias necesarias...")
    
    for dep in dependencies:
        try:
            if dep == "pyinstaller":
                import PyInstaller
            elif dep == "pillow":
                from PIL import Image
            elif dep == "requests":
                import requests
            print(f"  ✓ {dep} ya está instalado")
        except ImportError:
            missing_deps.append(dep)
            print(f"  ✗ {dep} no está instalado")
    
    if missing_deps:
        print(f"\nInstalando dependencias faltantes: {', '.join(missing_deps)}")
        try:
            for dep in missing_deps:
                print(f"  Instalando {dep}...")
                run([sys.executable, "-m", "pip", "install", dep, "--quiet"], 
                    check=True, stdout=sys.stdout, stderr=sys.stderr)
                print(f"  ✓ {dep} instalado exitosamente")
            return True
        except CalledProcessError as e:
            print(f"ERROR: No se pudieron instalar las dependencias. {e}")
            print("\nInstala manualmente con:")
            print("  pip install requests pyinstaller pillow")
            return False
    else:
        print("\n✅ Todas las dependencias están instaladas.")
        return True
     
     
def install_pyinstaller():
    """Instala PyInstaller y todas las dependencias necesarias."""
    clear_console("PASO 4: Verificando e instalando dependencias")
    
    # Si estamos ejecutando desde EXE, necesitamos Python del sistema
    if is_running_from_exe():
        print("Ejecutando desde .exe - verificando Python del sistema...")
        
        # Verificar que Python esté disponible
        python_available = check_python_available()
        
        if not python_available:
            print("\n⚠️  ADVERTENCIA: Python no está disponible en el sistema.")
            print("Para compilar ejecutables, necesitas:")
            print("1. Instalar Python desde: https://python.org")
            print("2. Ejecutar estos comandos en CMD como Administrador:")
            print("   pip install requests")
            print("   pip install pyinstaller")
            print("   pip install pillow")
            print("\n¿Deseas continuar sin compilar el .exe? (s/n): ", end="")
            respuesta = input().strip().lower()
            
            if respuesta != 's':
                print("Compilación cancelada por el usuario.")
                return False
            else:
                print("Continuando sin compilar .exe...")
                return False
        return True
    
    # Ejecución normal desde Python - instalar todas las dependencias
    return install_required_dependencies()

def download_icon(project_dir):
    """Descarga el icono personalizado ICO directamente desde GitHub."""
    icon_url = "https://raw.githubusercontent.com/JhonPizaVision/VisionyMarketing/main/Scripts/icono_exe.png"
    icon_path = project_dir / "icono_exe.png"
    
    try:
        # Descargar el icono ICO directamente
        response = exponential_backoff_fetch(icon_url)
        if response and response.status_code == 200:
            with open(icon_path, 'wb') as f:
                f.write(response.content)
            print(f"Icono personalizado descargado: {icon_path.name}")
            
            # Verificar que el archivo ICO es válido
            try:
                from PIL import Image
                with Image.open(icon_path) as img:
                    print(f"  - Formato verificado: {img.format}, Tamaño: {img.size}")
                return icon_path
            except ImportError:
                print("  - Pillow no disponible, no se pudo verificar el icono")
                return icon_path
            except Exception as e:
                print(f"ADVERTENCIA: El archivo ICO podría estar corrupto. {e}")
                return None
                
    except Exception as e:
        print(f"ADVERTENCIA: No se pudo descargar el icono personalizado. Se usará el icono por defecto. {e}")
    
    return None

def install_pillow_if_needed():
    """Instala Pillow si no está instalado para manejar iconos."""
    try:
        from PIL import Image
        return True
    except ImportError:
        print("Instalando Pillow para manejar iconos...")
        try:
            run([sys.executable, "-m", "pip", "install", "pillow"], 
                check=True, stdout=sys.stdout, stderr=sys.stderr)
            print("Pillow instalado exitosamente.")
            return True
        except Exception as e:
            print(f"ADVERTENCIA: No se pudo instalar Pillow. {e}")
            return False

   
def compile_to_exe(script_path, client, project):
    """Compila el script de ejecución a un archivo .exe usando PyInstaller."""
    clear_console("PASO 5: Compilando a Ejecutable (.exe)")
    
    if not install_pyinstaller():
        print("\n⚠️  No se pudo proceder con la compilación.")
        print(f"El proyecto se descargó exitosamente en: {script_path.parent}")
        print(f"Puedes ejecutar el script directamente: python {script_path.name}")
        return None
        
    exe_name = f"RUN_{project}.exe"
    project_dir = script_path.parent
    
    print(f"Iniciando compilación de {script_path.name} a {exe_name}...")
    
    try:
        # Descargar el icono personalizado ICO directamente
        icon_path = download_icon(project_dir)
        
        # Construir comando de PyInstaller con TODAS las dependencias necesarias
        if is_running_from_exe():
            # Cuando se ejecuta desde EXE, no podemos usar el comando pyinstaller directamente
            print("Ejecutando desde .exe, usando Python del sistema para compilar...")
            
            # Intentar encontrar python en el sistema
            python_path = shutil.which("python") or shutil.which("python.exe")
            if python_path:
                cmd = [
                    python_path,
                    "-m", "PyInstaller",
                    "--onefile",
                    "--distpath", str(project_dir),
                    "--name", exe_name,
                    "--noconfirm",
                    "--clean",
                    "--log-level=WARN",
                    # Desactivar UPX para evitar problemas
                    "--noupx",
                    # Incluir TODAS las dependencias necesarias
                    "--hidden-import=queue",
                    "--hidden-import=json",
                    "--hidden-import=requests",
                    "--hidden-import=pathlib",
                    "--hidden-import=subprocess",
                    "--hidden-import=re",
                    "--hidden-import=os",
                    "--hidden-import=sys",
                    "--hidden-import=shutil",
                    "--hidden-import=time",
                    "--hidden-import=io",
                    "--hidden-import=urllib3",
                    "--hidden-import=chardet",
                    "--hidden-import=idna",
                    "--hidden-import=certifi",
                    "--hidden-import=ssl",
                    # Agregar datos adicionales
                    "--add-data", ".;."
                ]
                
                # Agregar icono si está disponible
                if icon_path and icon_path.exists():
                    cmd.extend(["--icon", str(icon_path)])
                    print(f"Usando icono personalizado: {icon_path.name}")
                else:
                    print("Usando icono por defecto de PyInstaller")
                
                print(f"Usando Python del sistema: {python_path}")
            else:
                print("ERROR: No se encontró Python en el sistema.")
                print("Instala Python y vuelve a ejecutar ProjectDeployer.")
                return None
        else:
            # Ejecución normal desde Python
            cmd = [
                sys.executable,
                "-m", "PyInstaller",
                "--onefile",
                "--distpath", str(project_dir),
                "--name", exe_name,
                "--noconfirm",
                "--clean",
                "--log-level=WARN",
                # Desactivar UPX para evitar problemas
                "--noupx",
                # Incluir TODAS las dependencias necesarias
                "--hidden-import=queue",
                "--hidden-import=json",
                "--hidden-import=requests",
                "--hidden-import=pathlib",
                "--hidden-import=subprocess",
                "--hidden-import=re",
                "--hidden-import=os",
                "--hidden-import=sys",
                "--hidden-import=shutil",
                "--hidden-import=time",
                "--hidden-import=io",
                "--hidden-import=urllib3",
                "--hidden-import=chardet",
                "--hidden-import=idna",
                "--hidden-import=certifi",
                "--hidden-import=ssl",
                # Agregar datos adicionales
                "--add-data", ".;."
            ]
            
            # Agregar icono si está disponible
            if icon_path and icon_path.exists():
                cmd.extend(["--icon", str(icon_path)])
                print(f"Usando icono personalizado: {icon_path.name}")
            else:
                print("Usando icono por defecto de PyInstaller")
        
        # Agregar el script a compilar al final
        cmd.append(str(script_path))
        
        print(f"Ejecutando PyInstaller... (esto puede tardar varios minutos)")
        print(f"Incluyendo dependencias: requests, json, os, sys, etc.")
        
        # Ejecutar PyInstaller
        run(cmd, check=True, stdout=sys.stdout, stderr=sys.stderr)
            
        final_exe_path = project_dir / exe_name
        
        # Limpiar archivos temporales de PyInstaller
        clean_pyinstaller_temp_files(project_dir, project)
        
        # Opcional: Eliminar el archivo de icono después de la compilación
        if icon_path and icon_path.exists():
            try:
                icon_path.unlink()
                print(f"  - Archivo de icono temporal eliminado: {icon_path.name}")
            except Exception as e:
                print(f"ADVERTENCIA: No se pudo eliminar el archivo de icono. {e}")

        if final_exe_path.exists():
            # Verificar que el ejecutable es válido
            file_size = final_exe_path.stat().st_size
            if file_size > 5000000:  # Más de 5MB (con todas las dependencias)
                print(f"✅ Compilación exitosa. Ejecutable creado en: {final_exe_path}")
                print(f"  - Tamaño del ejecutable: {file_size / (1024*1024):.2f} MB")
                print(f"  - Dependencias incluidas: requests, json, os, sys, etc.")
                
                return final_exe_path
            else:
                print("⚠️  ADVERTENCIA: El ejecutable parece ser muy pequeño.")
                print(f"  - Tamaño: {file_size} bytes (debería ser >5MB con dependencias)")
                print("  - Probablemente no incluyó todas las dependencias.")
                return None
        else:
            print(f"ERROR: PyInstaller finalizó, pero no se encontró el archivo de salida esperado: {final_exe_path}")
            return None
            
    except CalledProcessError as e:
        print(f"ERROR: La compilación con PyInstaller falló. {e}")
        print("\nSolución: Instalar dependencias manualmente y volver a intentar.")
        print("Comandos a ejecutar:")
        print("  pip install requests")
        print("  pip install pyinstaller")
        print("  pip install pillow")
        return None
    except FileNotFoundError as e:
        print(f"ERROR: No se pudo encontrar el ejecutable de Python o PyInstaller.")
        print("  - Asegúrate de que Python esté instalado en el sistema.")
        print("  - Verifica que PyInstaller esté instalado: pip install pyinstaller")
        print("  - Verifica que requests esté instalado: pip install requests")
        return None
    except Exception as e:
        print(f"ERROR inesperado durante la compilación: {e}")
        print("\nPuedes ejecutar el script .py directamente (requiere Python instalado):")
        print(f"  1. Instalar dependencias: pip install requests")
        print(f"  2. Navegar a: {project_dir}")
        print(f"  3. Ejecutar: python RUN_{project}.py")
        return None

def clean_pyinstaller_temp_files(project_dir, project):
    """Limpia todos los archivos temporales de PyInstaller."""
    try:
        # Eliminar carpeta build
        build_dir = Path("build")
        if build_dir.exists():
            shutil.rmtree(build_dir, ignore_errors=True)
        
        # Eliminar archivo .spec
        spec_file = Path(f"RUN_{project}.spec")
        if spec_file.exists():
            spec_file.unlink()
            
        # Limpiar también desde BASE_DIR por si acaso
        build_dir_base = BASE_DIR / "build"
        spec_file_base = BASE_DIR / f"RUN_{project}.spec"
        
        shutil.rmtree(build_dir_base, ignore_errors=True)
        if spec_file_base.exists():
            spec_file_base.unlink()
            
        print("  - Archivos temporales de PyInstaller eliminados.")
        
    except Exception as e:
        print(f"ADVERTENCIA: Error limpiando archivos temporales: {e}")

def create_desktop_shortcut(exe_path, project):
    """Copia el ejecutable directamente al escritorio detectando la ruta real."""
    clear_console("PASO 6: Copiando Ejecutable al Escritorio")
    
    try:
        # Método 1: Usar la variable de entorno de Windows para el escritorio
        desktop_path = Path(os.environ.get('USERPROFILE')) / 'Desktop'
        
        # Método 2: Si no existe, intentar con la ruta de OneDrive
        if not desktop_path.exists():
            onedrive_path = Path(os.environ.get('ONEDRIVE')) or Path.home()
            desktop_path = onedrive_path / 'Desktop'
            
        # Método 3: Si todavía no existe, usar la ruta por defecto
        if not desktop_path.exists():
            desktop_path = Path.home() / 'Desktop'
            
        # Método 4: Último recurso - buscar en el registro de Windows
        if not desktop_path.exists():
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                   r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
                desktop_reg, _ = winreg.QueryValueEx(key, "Desktop")
                winreg.CloseKey(key)
                desktop_path = Path(desktop_reg.replace('%USERPROFILE%', str(Path.home())))
            except:
                pass

        # Si después de todo no encontramos el escritorio, mostrar error
        if not desktop_path.exists():
            print(f"ADVERTENCIA: No se pudo encontrar la carpeta del escritorio.")
            print(f"  - El ejecutable está en: {exe_path}")
            print(f"  - Cópielo manualmente a su escritorio")
            return

        desktop_exe_path = desktop_path / f"RUN_{project}.exe"

        # Copiar el ejecutable al escritorio
        shutil.copy2(exe_path, desktop_exe_path)
        print(f"Ejecutable copiado al escritorio: {desktop_exe_path}")
        
    except Exception as e:
        print(f"ERROR: No se pudo copiar el ejecutable al escritorio. {e}")
        print(f"  - El ejecutable está en: {exe_path}")
        print(f"  - Cópielo manualmente a su escritorio")


def main():
    """Función principal de la aplicación."""
    
    # Detección de ejecución desde EXE
    if is_running_from_exe():
        print("🔧 EJECUTANDO DESDE ARCHIVO COMPILADO")
        print("Nota: Algunas funcionalidades pueden requerir Python instalado en el sistema.")
        print()
    
    # 0. Asegurar directorios base
    ensure_base_directories()
    
    # 1. Obtener entradas
    client, project = get_user_input()
    project_dir = BASE_DIR / client / project
    
    # --- DESPLIEGUE INICIAL (Descarga y Configuración del VENV) ---
    
    # 2. Descargar archivos del proyecto
    clear_console(f"PASO 1: Descargando archivos del proyecto {project}")
    success, downloaded_files = download_project_files(client, project, project_dir)
    if not success:
        print("\nDespliegue inicial fallido: No se pudo descargar el proyecto.")
        return
    print(f"\nDescarga de archivos del proyecto completada ({len(downloaded_files)} archivos).")

    # 3. Chequear variables de entorno
    check_env_variables(project_dir, project)

    # 4. Configurar VENV e instalar requerimientos
    venv_path = setup_virtual_environment(project_dir, project)
    
    if not venv_path:
        print("\nERROR CRÍTICO: El VENV no se configuró correctamente. Abortando compilación.")
        return
        
    # --- PROCESO DE GENERACIÓN Y COMPILACIÓN DEL EJECUTABLE ---

    # 5. Generar el script de ejecución dinámico (RUN_PROJECT.py)
    executor_script_path = generate_executor_script(client, project, project_dir)
    print(f"\nScript de ejecución generado en: {executor_script_path.name}")

    # 6. Compilar el script de ejecución a .exe
    final_exe_path = compile_to_exe(executor_script_path, client, project)
    
    # 7. Limpieza: eliminar el archivo .py temporal que acabamos de compilar
    try:
        os.remove(executor_script_path)
        print(f"  - Archivo temporal '{executor_script_path.name}' eliminado.")
    except Exception as e:
         print(f"ADVERTENCIA: No se pudo eliminar el archivo temporal. {e}")

    if final_exe_path:
        # 8. Crear acceso directo en el escritorio
        create_desktop_shortcut(final_exe_path, project)
        
        # 9. Eliminar el archivo _VERSION.txt (el ejecutable lo obtendrá del repo si es necesario)
        version_file_path = project_dir / f"{project}_VERSION.txt"
        if version_file_path.exists():
             try:
                os.remove(version_file_path)
                print(f"\n  - Archivo temporal de versión eliminado: {version_file_path.name}")
             except Exception as e:
                 print(f"ADVERTENCIA: No se pudo eliminar el archivo de versión temporal. {e}")

        print("\n--- ¡DESPLIEGUE INICIAL Y COMPILACIÓN COMPLETOS! ---")
        print(f"El proyecto está configurado. Use el acceso directo o el ejecutable '{final_exe_path.name}' para ejecutarlo.")
    else:
        print("\nERROR: El proceso de compilación falló. El proyecto se descargó, pero no se generó el .exe.")

if __name__ == "__main__":
    main()
