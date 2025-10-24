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
