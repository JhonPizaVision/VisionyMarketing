// Configuración global de la aplicación
const CONFIG = {
    usuario: "JhonPizaVision",
    repositorio: "VisionyMarketing",
    baseURL: `https://api.github.com/repos/JhonPizaVision/VisionyMarketing/git/trees/main?recursive=1`,
    rutaBase: "DocumentosClientes",
    token: null // se cargará dinámicamente desde el archivo .env
};

// Cargar token desde el archivo .env (solo en entorno local / servidor con soporte)
(async () => {
    try {
        // Intentamos cargar el archivo .env
        const response = await fetch('/.env');
        if (response.ok) {
            const text = await response.text();
            const match = text.match(/^GITHUB_TOKEN=(.*)$/m);
            if (match) {
                CONFIG.token = match[1].trim();
                console.log("✅ Token de GitHub cargado correctamente desde .env");
            } else {
                console.warn("⚠️ No se encontró GITHUB_TOKEN en el archivo .env");
            }
        } else {
            console.warn("⚠️ No se pudo acceder al archivo .env (probablemente por seguridad del servidor)");
        }
    } catch (error) {
        console.error("Error cargando el token desde .env:", error);
    }
})();

// Obtener ruta actual desde URL
const params = new URLSearchParams(window.location.search);
const rutaActual = params.get("ruta") || CONFIG.rutaBase;
