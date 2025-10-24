// Configuración global de la aplicación
const CONFIG = {
    usuario: "JhonPizaVision",
    repositorio: "VisionyMarketing",
    baseURL: `https://api.github.com/repos/JhonPizaVision/VisionyMarketing/git/trees/main?recursive=1`,
    rutaBase: "DocumentosClientes",
    // Token codificado en Base64 - GitHub puede detectarlo igualmente
    tokenCodificado: "Z2l0aHViX3BhdF8xMUJRSktVTEEwQ3ZPSXJ6N3NjZmpQX0dvdmhVMW5SOUU4YnN2SlZNdGV2YWJ5SXJTbk91bE1RZFp4YTJVWjdicGNUT09BS1NBSmNzdTZJbHZx"
};

// Función para decodificar el token
CONFIG.getToken = function() {
    try {
        return atob(this.tokenCodificado);
    } catch (error) {
        console.error('Error decodificando token:', error);
        return null;
    }
};

// Obtener ruta actual desde URL
const params = new URLSearchParams(window.location.search);
const rutaActual = params.get("ruta") || CONFIG.rutaBase;
