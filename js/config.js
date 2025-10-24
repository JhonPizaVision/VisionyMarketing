// Configuración global de la aplicación
const CONFIG = {
    usuario: "JhonPizaVision",
    repositorio: "VisionyMarketing",
    baseURL: `https://api.github.com/repos/JhonPizaVision/VisionyMarketing/git/trees/main?recursive=1`,
    rutaBase: "DocumentosClientes",
    token: process.env.TOKEN
};

// Obtener ruta actual desde URL
const params = new URLSearchParams(window.location.search);
const rutaActual = params.get("ruta") || CONFIG.rutaBase;
