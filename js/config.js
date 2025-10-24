// Configuración global de la aplicación
const CONFIG = {
    usuario: "JhonPizaVision",
    repositorio: "VisionyMarketing",
    baseURL: `https://api.github.com/repos/JhonPizaVision/VisionyMarketing/git/trees/main?recursive=1`,
    rutaBase: "DocumentosClientes",
    // Token de GitHub - Reemplaza con tu token real
    token: "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"
};

// Obtener ruta actual desde URL
const params = new URLSearchParams(window.location.search);
const rutaActual = params.get("ruta") || CONFIG.rutaBase;
