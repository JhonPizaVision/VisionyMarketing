import os
import sys
import shutil
from pathlib import Path
from subprocess import run, CalledProcessError
import requests

def clear_console(step_name):
    """Borra la consola para una presentación más limpia."""
    print(f"\n{'=' * 50}\n-> {step_name}\n{'=' * 50}")

def download_icon_for_deployer():
    """Descarga el icono para el project_deployer.exe"""
    icon_url = "https://raw.githubusercontent.com/JhonPizaVision/VisionyMarketing/main/Scripts/icono_exe.ico"
    icon_path = Path("icono_deployer.ico")
    
    try:
        response = requests.get(icon_url)
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
            run([sys.executable, "-m", "pip", "install", "pyinstaller", "--upgrade"], 
                check=True, stdout=sys.stdout, stderr=sys.stderr)
            print("PyInstaller instalado exitosamente.")
            return True
        except CalledProcessError as e:
            print(f"ERROR: No se pudo instalar PyInstaller. {e}")
            return False

def clean_pyinstaller_files():
    """Limpia archivos temporales de PyInstaller."""
    files_to_clean = [
        "build",
        "project_deployer.spec",
        "icono_deployer.ico"
    ]
    
    for item in files_to_clean:
        if os.path.exists(item):
            if os.path.isdir(item):
                shutil.rmtree(item, ignore_errors=True)
            else:
                os.remove(item)
            print(f"  - Eliminado: {item}")

def compile_project_deployer():
    """Compila project_deployer.py a ejecutable."""
    clear_console("COMPILANDO PROJECT_DEPLOYER")
    
    # Verificar que el archivo existe
    if not os.path.exists("project_deployer.py"):
        print("ERROR: No se encuentra project_deployer.py en el directorio actual.")
        return False
    
    # Instalar PyInstaller si es necesario
    if not install_pyinstaller_if_needed():
        return False
    
    # Descargar icono
    icon_path = download_icon_for_deployer()
    
    # Construir comando de PyInstaller
    cmd = [
        "pyinstaller",
        "--onefile",
        "--name", "ProjectDeployer",
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
    
    print(f"Ejecutando: {' '.join(cmd)}")
    
    try:
        # Compilar
        run(cmd, check=True, stdout=sys.stdout, stderr=sys.stderr)
        
        # Verificar que el ejecutable se creó
        exe_path = Path("dist") / "ProjectDeployer.exe"
        if exe_path.exists():
            print(f"\n✅ COMPILACIÓN EXITOSA!")
            print(f"Ejecutable creado en: {exe_path}")
            print(f"Tamaño: {exe_path.stat().st_size / (1024*1024):.2f} MB")
            
            # Copiar al directorio actual para fácil acceso
            shutil.copy2(exe_path, "ProjectDeployer.exe")
            print(f"También copiado a: ProjectDeployer.exe")
            
            return True
        else:
            print("ERROR: PyInstaller no generó el ejecutable esperado.")
            return False
            
    except CalledProcessError as e:
        print(f"ERROR en la compilación: {e}")
        return False
    finally:
        # Limpiar archivos temporales
        clear_console("LIMPIEZA")
        clean_pyinstaller_files()

def main():
    """Función principal."""
    print("COMPILADOR DE PROJECT_DEPLOYER")
    print("Este script convertirá project_deployer.py en un ejecutable.")
    
    success = compile_project_deployer()
    
    if success:
        print("\n" + "="*60)
        print("🎉 ¡PROJECT_DEPLOYER COMPILADO EXITOSAMENTE!")
        print("="*60)
        print("Ahora puedes usar 'ProjectDeployer.exe' directamente.")
        print("No necesitarás Python instalado en las computadoras destino.")
    else:
        print("\n❌ La compilación falló. Revisa los mensajes de error.")

if __name__ == "__main__":
    main()