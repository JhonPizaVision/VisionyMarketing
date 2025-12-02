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

def create_readme():
    """Crea un archivo README.txt con información del autor y uso."""
    readme_content = """PROJECT DEPLOYER - JHON PIZA - INNOVATIONS BI
===================================================

DESCRIPCIÓN:
------------
Project Deployer es una herramienta para automatizar el despliegue de proyectos 
Python desde GitHub. Descarga, configura y compila scripts automáticamente.

CARACTERÍSTICAS:
----------------
• Descarga automática de proyectos desde GitHub
• Configuración de variables de entorno
• Creación de entornos virtuales
• Compilación a ejecutables .exe
• Actualización automática de versiones
• Iconos personalizados

USO:
----
1. Ejecutar ProjectDeployer.exe
2. Ingresar nombre del CLIENTE
3. Ingresar nombre del PROYECTO
4. El sistema hará el resto automáticamente

AUTOR:
------
JHON PIZA - INNOVATIONS BI
Sistema automatizado para despliegue de proyectos

VERSIÓN: 1.0
FECHA: """ + time.strftime("%d/%m/%Y")

    with open("README.txt", "w", encoding="utf-8") as f:
        f.write(readme_content)
    print("Archivo README.txt creado.")

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
    """Función principal."""
    import time
    
    print_banner()
    
    start_time = time.time()
    success, zip_name = compile_project_deployer()
    
    if success and zip_name:
        print("\n" + "="*60)
        print("🎉 ¡PROJECT_DEPLOYER COMPILADO Y EMPAQUETADO EXITOSAMENTE!")
        print("="*60)
        print(f"Archivo ZIP creado: {zip_name}")
        print("\nINSTRUCCIONES:")
        print("1. Distribuye el archivo ZIP a los usuarios")
        print("2. Los usuarios deben extraer el contenido")
        print("3. Ejecutar 'ProjectDeployer_JhonPiza.exe'")
        print("\nVENTAJAS:")
        print("• No requiere Python instalado en las computadoras destino")
        print("• Sistema automático de actualización")
        print("• Fácil distribución y uso")
        
        elapsed_time = time.time() - start_time
        print(f"\n⏱️  Tiempo total del proceso: {elapsed_time:.2f} segundos")
        
        # Mostrar información final
        if os.path.exists(zip_name):
            zip_size = os.path.getsize(zip_name) / (1024*1024)
            print(f"📦 Tamaño del paquete final: {zip_size:.2f} MB")
            
    elif success:
        print("\n" + "="*60)
        print("✅ PROJECT_DEPLOYER COMPILADO EXITOSAMENTE")
        print("="*60)
        print("Archivo ejecutable creado: ProjectDeployer_JhonPiza.exe")
        print("Nota: El archivo no fue comprimido a ZIP.")
    else:
        print("\n" + "="*60)
        print("❌ La compilación falló. Revisa los mensajes de error.")
        print("="*60)

if __name__ == "__main__":
    main()