// Configuración global de la aplicación
const CONFIG = {
    usuario: "JhonPizaVision",
    repositorio: "VisionyMarketing",
    baseURL: `https://api.github.com/repos/JhonPizaVision/VisionyMarketing/git/trees/main?recursive=1`,
    rutaBase: "DocumentosClientes"
};

// Función para obtener el token (ahora se pide al usuario)
CONFIG.getToken = function() {
    return sessionStorage.getItem('github_token');
};

// Función para guardar el token
CONFIG.setToken = function(token) {
    sessionStorage.setItem('github_token', token);
};

// Función para eliminar el token
CONFIG.clearToken = function() {
    sessionStorage.removeItem('github_token');
};

// Verificar si hay token
CONFIG.hasToken = function() {
    return !!this.getToken();
};

// Obtener ruta actual desde URL
const params = new URLSearchParams(window.location.search);
const rutaActual = params.get("ruta") || CONFIG.rutaBase;
