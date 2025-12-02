import os
import sys
import shutil
import zipfile
from pathlib import Path
from subprocess import run, CalledProcessError
import requests
import time

def print_banner():
    """Muestra el banner con autor."""
    print("=" * 60)
    print("COMPILADOR DE PROJECT_DEPLOYER")
    print("Autor: JHON PIZA - INNOVATIONS BI")
    print("=" * 60)
    print("Este script convertirá project_deployer.py en un ejecutable.")
    print()

def clear_console(step_name):
    """Borra la consola para una presentación más limpia."""
    print(f"\n{'=' * 50}\n-> {step_name}\n{'=' * 50}")

def download_icon_for_deployer():
    """Descarga el icono para el project_deployer.exe"""
    icon_url = "https://raw.githubusercontent.com/JhonPizaVision/VisionyMarketing/main/Scripts/icono_exe.ico"
    icon_path = Path("icono_deployer.ico")
    
    try:
        response = requests.get(icon_url, timeout=10)
        if response.status_code == 200:
            with open(icon_path, 'wb') as f:
                f.write(response.content)
            print(f"Icono descargado: {icon_path}")
            return icon_path
    except Exception as e:
        print(f"ADVERTENCIA: No se pudo descargar el icono. {e}")
    
    return None

def install_pyinstaller_if_needed():
    """Instala PyInstaller si no está disponible."""
    try:
        import PyInstaller
        print("PyInstaller ya está instalado.")
        return True
    except ImportError:
        print("Instalando PyInstaller...")
        try:
            run([sys.executable, "-m", "pip", "install", "pyinstaller", "--upgrade", "--quiet"], 
                check=True, stdout=sys.stdout, stderr=sys.stderr)
            print("PyInstaller instalado exitosamente.")
            return True
        except CalledProcessError as e:
            print(f"ERROR: No se pudo instalar PyInstaller. {e}")
            return False

def create_readme_instructions(project_dir, project, client):
    """Crea un archivo README_INSTRUCCIONES.txt con pasos detallados."""
    readme_content = f"""INSTRUCCIONES PARA EJECUTAR PROYECTO: {project}
CLIENTE: {client}
AUTOR: JHON PIZA - INNOVATIONS BI
==============================================================

OPCIÓN 1: EJECUTAR DIRECTAMENTE (Requiere Python)
-------------------------------------------------
1. Instalar Python desde: https://python.org
2. Instalar dependencias necesarias:
   pip install requests
   pip install pyinstaller  (solo si quieres compilar)
   pip install pillow       (solo si quieres compilar)
3. Navegar a la carpeta:
   cd "{project_dir}"
4. Ejecutar el script:
   python RUN_{project}.py

OPCIÓN 2: USAR EL EJECUTABLE .EXE
---------------------------------
1. Si ya tienes RUN_{project}.exe, haz doble clic en él.
2. Si el .exe da error, reinstalar dependencias y recompilar.

OPCIÓN 3: COMPILAR NUEVO .EXE
------------------------------
1. Asegúrate de tener Python instalado.
2. Instalar dependencias (ejecutar en CMD como Administrador):
   pip install requests
   pip install pyinstaller
   pip install pillow
3. Navegar a la carpeta:
   cd "{project_dir}"
4. Compilar:
   pyinstaller --onefile --hidden-import=requests --hidden-import=json RUN_{project}.py

SOLUCIÓN DE PROBLEMAS COMUNES:
------------------------------
1. Error "No module named 'requests'":
   Ejecutar: pip install requests

2. Error "No module named 'PIL'":
   Ejecutar: pip install pillow

3. El .exe no se ejecuta:
   - Verificar que el archivo no esté corrupto
   - Recompilar con las dependencias incluidas
   - Usar la opción de ejecutar con Python

4. Error de permisos:
   Ejecutar CMD/PowerShell como Administrador

CONTACTO Y SOPORTE:
-------------------
Sistema desarrollado por JHON PIZA - INNOVATIONS BI
Para soporte técnico, contactar al administrador.

FECHA: {time.strftime("%d/%m/%Y")}
"""

    readme_path = project_dir / "README_INSTRUCCIONES.txt"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    return readme_path

def compress_to_zip(exe_path, zip_name="ProjectDeployer_JhonPiza.zip"):
    """Comprime el ejecutable a un archivo ZIP."""
    clear_console("COMPRIMIENDO A ZIP")
    
    try:
        with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Agregar el ejecutable
            zipf.write(exe_path.name, arcname=exe_path.name)
            print(f"  - Agregado: {exe_path.name}")
            
            # Agregar README si existe
            if os.path.exists("README.txt"):
                zipf.write("README.txt", arcname="README.txt")
                print(f"  - Agregado: README.txt")
            
            # Agregar icono si existe
            if os.path.exists("icono_deployer.ico"):
                zipf.write("icono_deployer.ico", arcname="icono_deployer.ico")
                print(f"  - Agregado: icono_deployer.ico")
            
        print(f"\n✅ Archivo ZIP creado: {zip_name}")
        
        # Mostrar información del ZIP
        zip_size = os.path.getsize(zip_name) / (1024*1024)
        print(f"  - Tamaño del ZIP: {zip_size:.2f} MB")
        
        return zip_name
    except Exception as e:
        print(f"❌ Error al crear archivo ZIP: {e}")
        return None

def clean_pyinstaller_files():
    """Limpia archivos temporales de PyInstaller."""
    files_to_clean = [
        "build",
        "dist",
        "project_deployer.spec",
        "icono_deployer.ico",
        "README.txt"
    ]
    
    print("Limpiando archivos temporales...")
    for item in files_to_clean:
        if os.path.exists(item):
            try:
                if os.path.isdir(item):
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    os.remove(item)
                print(f"  - Eliminado: {item}")
            except Exception as e:
                print(f"  - ADVERTENCIA: No se pudo eliminar {item}: {e}")

def cleanup_exe_files(exe_paths):
    """Elimina archivos .exe después de comprimir."""
    print("\nLimpiando archivos .exe temporales...")
    for exe_path in exe_paths:
        if os.path.exists(exe_path):
            try:
                os.remove(exe_path)
                print(f"  - Eliminado: {exe_path}")
            except Exception as e:
                print(f"  - ADVERTENCIA: No se pudo eliminar {exe_path}: {e}")

def compile_project_deployer():
    """Compila project_deployer.py a ejecutable."""
    clear_console("COMPILANDO PROJECT_DEPLOYER")
    
    # Verificar que el archivo existe
    if not os.path.exists("project_deployer.py"):
        print("❌ ERROR: No se encuentra project_deployer.py en el directorio actual.")
        return False
    
    # Instalar PyInstaller si es necesario
    if not install_pyinstaller_if_needed():
        return False
    
    # Descargar icono
    icon_path = download_icon_for_deployer()
    
    # Crear README
    create_readme()
    
    # Construir comando de PyInstaller
    cmd = [
        "pyinstaller",
        "--onefile",
        "--name", "ProjectDeployer_JhonPiza",
        "--noconfirm",
        "--clean"
    ]
    
    # Agregar icono si está disponible
    if icon_path and icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])
        print("Usando icono personalizado")
    else:
        print("Usando icono por defecto")
    
    # Agregar el script principal
    cmd.append("project_deployer.py")
    
    print(f"\nEjecutando PyInstaller...")
    print(f"Comando: {' '.join(cmd[:5])}... {cmd[-1]}")
    
    try:
        # Compilar
        run(cmd, check=True, stdout=sys.stdout, stderr=sys.stderr)
        
        # Verificar que el ejecutable se creó
        exe_name = "ProjectDeployer_JhonPiza.exe"
        exe_path = Path("dist") / exe_name
        exe_path_current = Path(exe_name)
        
        if exe_path.exists():
            # Copiar al directorio actual
            shutil.copy2(exe_path, exe_path_current)
            
            print(f"\n✅ COMPILACIÓN EXITOSA!")
            print(f"Ejecutable creado en: {exe_path_current}")
            print(f"Tamaño: {exe_path_current.stat().st_size / (1024*1024):.2f} MB")
            
            # Comprimir a ZIP
            zip_name = compress_to_zip(exe_path_current)
            
            # Limpiar archivos .exe
            exe_files = [exe_path_current, exe_path]
            cleanup_exe_files(exe_files)
            
            return True, zip_name
        else:
            print("❌ ERROR: PyInstaller no generó el ejecutable esperado.")
            return False, None
            
    except CalledProcessError as e:
        print(f"❌ ERROR en la compilación: {e}")
        return False, None
    finally:
        # Limpiar archivos temporales
        clear_console("LIMPIEZA FINAL")
        clean_pyinstaller_files()

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
    
    # --- DESPLIEGUE INICIAL ---
    
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
        print("\nERROR CRÍTICO: El VENV no se configuró correctamente.")
        return
        
    # 5. Generar el script de ejecución
    executor_script_path = generate_executor_script(client, project, project_dir)
    print(f"\nScript de ejecución generado en: {executor_script_path.name}")

    # 6. Crear archivo de instrucciones
    readme_path = create_readme_instructions(project_dir, project, client)
    print(f"Archivo de instrucciones creado: {readme_path.name}")

    # 7. Preguntar sobre compilación
    print("\n" + "="*60)
    print("OPCIONES DE EJECUCIÓN:")
    print("1. Compilar a .exe (requiere Python y PyInstaller instalados)")
    print("2. Crear archivo .bat para ejecutar con Python")
    print("3. Solo generar archivos, ejecutar manualmente después")
    print("="*60)
    
    opcion = input("\nSeleccione opción (1/2/3) [1]: ").strip()
    
    if opcion == "" or opcion == "1":
        # Intentar compilar
        print("\nIntentando compilar a .exe...")
        print("NOTA: Esto requiere tener instalado:")
        print("  - Python (https://python.org)")
        print("  - PyInstaller (pip install pyinstaller)")
        print("  - Requests (pip install requests)")
        print("  - Pillow (pip install pillow)")
        
        final_exe_path = compile_to_exe(executor_script_path, client, project)
        
        if final_exe_path:
            create_desktop_shortcut(final_exe_path, project)
            print("\n✅ COMPILACIÓN EXITOSA!")
            print(f"Ejecutable: {final_exe_path.name}")
        else:
            print("\n⚠️  La compilación falló. Creando alternativa .bat...")
            bat_path = create_bat_file(project_dir, project, client)
            create_desktop_shortcut_bat(bat_path, project)
            print(f"✅ Se creó archivo .bat: {bat_path.name}")
    
    elif opcion == "2":
        # Crear solo archivo .bat
        bat_path = create_bat_file(project_dir, project, client)
        create_desktop_shortcut_bat(bat_path, project)
        print(f"\n✅ Se creó archivo .bat: {bat_path.name}")
        print("Ejecútalo haciendo doble clic (requiere Python instalado)")
    
    elif opcion == "3":
        print(f"\n✅ Archivos generados en: {project_dir}")
        print(f"Para ejecutar manualmente:")
        print(f"1. Navegar a: {project_dir}")
        print(f"2. Instalar dependencias: pip install requests")
        print(f"3. Ejecutar: python RUN_{project}.py")
    
    # 8. Mostrar instrucciones finales
    print("\n" + "="*60)
    print("INSTRUCCIONES FINALES:")
    print("="*60)
    print(f"1. Carpeta del proyecto: {project_dir}")
    print(f"2. Archivo de instrucciones: README_INSTRUCCIONES.txt")
    print(f"3. Script principal: RUN_{project}.py")
    print("\nSi encuentras errores, verifica que tengas instalado:")
    print("  - Python: https://python.org")
    print("  - Dependencias: pip install requests")
    print("="*60)
    
if __name__ == "__main__":
    main()