// Función principal para cargar contenido
async function cargarContenido() {
    const contenedor = document.getElementById("contenedor");
    const titulo = document.getElementById("titulo");
    const loader = document.getElementById("loader");

    try {
        // Mostrar loader y ocultar contenedor
        loader.classList.remove("hidden");
        contenedor.classList.add("hidden");

        const resp = await fetch(CONFIG.baseURL);
        const data = await resp.json();
        if (!data.tree) throw new Error("No se encontró contenido");

        // Filtrar elementos dentro de la ruta actual
        const nivelActual = data.tree.filter(item => {
            return item.path.startsWith(rutaActual + "/") && 
                   item.path !== rutaActual + "/";
        });

        // Extraer solo el siguiente nivel (carpetas o archivos directamente dentro)
        const items = new Map();
        const carpetasVistas = new Set();
        
        nivelActual.forEach(item => {
            const relativo = item.path.replace(rutaActual + "/", "");
            const partes = relativo.split("/");
            
            // Si es un archivo directo en la carpeta actual (sin subcarpetas)
            if (partes.length === 1 && relativo !== "") {
                const tieneExtension = partes[0].includes('.');
                if (tieneExtension) {
                    items.set(item.path, { 
                        tipo: "archivo", 
                        nombre: partes[0], 
                        path: item.path 
                    });
                }
            } 
            // Si hay subcarpetas
            else if (partes.length > 1) {
                const carpeta = partes[0];
                if (!carpetasVistas.has(carpeta)) {
                    carpetasVistas.add(carpeta);
                    items.set(carpeta, { 
                        tipo: "carpeta", 
                        nombre: carpeta, 
                        path: `${rutaActual}/${carpeta}` 
                    });
                }
            }
        });

        // Mostrar título
        titulo.textContent = rutaActual === CONFIG.rutaBase
            ? "Clientes"
            : `Contenido de ${rutaActual.split("/").slice(1).join(" / ")}`;

        contenedor.innerHTML = "";

        if (items.size === 0) {
            contenedor.innerHTML = "<p class='col-span-full text-center text-gray-600'>No hay contenido disponible.</p>";
        } else {
            // Convertir Map a Array y ordenar: carpetas primero, luego archivos
            const itemsOrdenados = Array.from(items.values()).sort((a, b) => {
                if (a.tipo === b.tipo) return a.nombre.localeCompare(b.nombre);
                return a.tipo === "carpeta" ? -1 : 1;
            });

            itemsOrdenados.forEach(item => {
                if (item.tipo === "carpeta") {
                    crearTarjetaCarpeta(item, contenedor);
                } else {
                    crearTarjetaArchivo(item, contenedor);
                }
            });
        }

        // Botón volver si no estamos en el nivel raíz
        if (rutaActual !== CONFIG.rutaBase) {
            crearBotonVolver(contenedor);
        }

    } catch (err) {
        console.error(err);
        contenedor.innerHTML = "<p class='text-center text-red-600'>Error al cargar contenido desde GitHub.</p>";
    } finally {
        // Ocultar loader y mostrar contenedor
        loader.classList.add("hidden");
        contenedor.classList.remove("hidden");
    }
}

// Función para crear tarjeta de carpeta
function crearTarjetaCarpeta(item, contenedor) {
    const card = document.createElement("a");
    card.href = `?ruta=${encodeURIComponent(item.path)}`;
    card.className = "bg-white rounded-xl shadow border border-gray-200 p-5 flex flex-col items-center text-center brand-hover cursor-pointer";
    card.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" class="h-12 w-12 text-blue-600 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7h18M3 7l3-3h15a2 2 0 012 2v12a2 2 0 01-2 2H3V7z" />
        </svg>
        <h3 class="text-md font-semibold text-gray-800">${item.nombre}</h3>
        <p class="text-sm text-gray-500 mt-1">Abrir carpeta</p>
    `;
    contenedor.appendChild(card);
}

// Función para crear tarjeta de archivo
function crearTarjetaArchivo(item, contenedor) {
    const urlPublica = `https://raw.githubusercontent.com/${CONFIG.usuario}/${CONFIG.repositorio}/main/${encodeURIComponent(item.path).replace(/%2F/g, "/")}`;
    const extension = item.nombre.split(".").pop().toLowerCase();

    const icono = obtenerIconoArchivo(extension);
    
    const card = document.createElement("a");
    card.href = urlPublica;
    card.target = "_blank";
    card.className = "bg-white rounded-xl shadow border border-gray-200 p-5 flex flex-col text-center brand-hover cursor-pointer";
    card.innerHTML = `
        ${icono}
        <p class="text-sm font-medium text-gray-700 truncate">${item.nombre}</p>
        <span class="text-xs text-gray-500 mt-1">${extension.toUpperCase()}</span>
    `;
    contenedor.appendChild(card);
}

// Función para obtener icono según extensión
function obtenerIconoArchivo(extension) {
    const iconos = {
        pdf: `<svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10 text-red-600 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>`,
        xlsx: `<svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10 text-green-600 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>`,
        xls: `<svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10 text-green-600 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>`,
        png: `<svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10 text-yellow-500 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>`,
        jpg: `<svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10 text-yellow-500 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>`,
        jpeg: `<svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10 text-yellow-500 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>`,
        doc: `<svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10 text-blue-600 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>`,
        docx: `<svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10 text-blue-600 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>`
    };

    return iconos[extension] || `<svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10 text-gray-500 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>`;
}

// Función para crear botón volver
function crearBotonVolver(contenedor) {
    const partes = rutaActual.split("/");
    partes.pop();
    const rutaPadre = partes.join("/");
    const volver = document.createElement("a");
    volver.href = `?ruta=${encodeURIComponent(rutaPadre || CONFIG.rutaBase)}`;
    volver.className = "block mt-8 text-center text-red-600 font-semibold underline cursor-pointer";
    volver.textContent = "← Volver";
    contenedor.after(volver);
}

// Inicializar
cargarContenido();