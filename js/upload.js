// Script para subir archivos a GitHub
document.addEventListener('DOMContentLoaded', function() {
    // Elementos del DOM
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const btnSeleccionar = document.getElementById('btnSeleccionar');
    const listaArchivos = document.getElementById('listaArchivos');
    const archivosContainer = document.getElementById('archivosContainer');
    const btnSubir = document.getElementById('btnSubir');
    const btnCancelar = document.getElementById('btnCancelar');
    const selectCliente = document.getElementById('selectCliente');
    const nuevoCliente = document.getElementById('nuevoCliente');
    const rutaCliente = document.getElementById('rutaCliente');
    const progresoContainer = document.getElementById('progresoContainer');
    const barraProgresoGlobal = document.getElementById('barraProgresoGlobal');
    const detalleProgreso = document.getElementById('detalleProgreso');
    const resultadosContainer = document.getElementById('resultadosContainer');
    const resultados = document.getElementById('resultados');

    // Variables globales
    let archivosSeleccionados = [];
    let clientesExistentes = [];

    // Inicializar
    inicializar();

    // Event listeners
    btnSeleccionar.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', manejarSeleccionArchivos);
    btnSubir.addEventListener('click', subirArchivos);
    btnCancelar.addEventListener('click', cancelarSubida);
    
    // Eventos para drag & drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, prevenirComportamiento, false);
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.add('active'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.remove('active'), false);
    });

    dropZone.addEventListener('drop', manejarDrop, false);

    // Eventos para selección de cliente
    selectCliente.addEventListener('change', validarFormulario);
    nuevoCliente.addEventListener('input', validarFormulario);
    rutaCliente.addEventListener('input', validarFormulario);

    // Funciones
    function inicializar() {
        // Verificar token
        if (!CONFIG.token || CONFIG.token === "ghp_tu_token_aqui") {
            mostrarErrorToken();
            return;
        }
        
        // Cargar clientes existentes
        cargarClientesExistentes();
    }

    function mostrarErrorToken() {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'p-4 bg-red-50 text-red-700 rounded-lg mb-6';
        errorDiv.innerHTML = `
            <div class="flex items-center">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
                <span class="font-medium">Token de GitHub no configurado</span>
            </div>
            <p class="text-sm mt-2">
                Para subir archivos, debes configurar un token de GitHub en el archivo <code class="bg-gray-100 px-1 rounded">config.js</code>.
            </p>
            <p class="text-sm mt-1">
                <strong>Instrucciones:</strong> Ve a GitHub → Settings → Developer settings → Personal access tokens → 
                Genera un nuevo token con permisos de "repo" y actualiza la variable <code class="bg-gray-100 px-1 rounded">CONFIG.token</code>.
            </p>
        `;
        
        // Insertar el mensaje de error al inicio del main
        const main = document.querySelector('main');
        const firstChild = main.firstElementChild;
        main.insertBefore(errorDiv, firstChild);
        
        // Deshabilitar controles
        btnSubir.disabled = true;
        btnSeleccionar.disabled = true;
        dropZone.style.opacity = '0.5';
        dropZone.style.pointerEvents = 'none';
    }

    async function cargarClientesExistentes() {
        try {
            const resp = await fetch(CONFIG.baseURL);
            const data = await resp.json();
            
            if (!data.tree) throw new Error("No se encontró contenido");

            // Extraer carpetas de clientes (primer nivel dentro de DocumentosClientes)
            const carpetas = data.tree
                .filter(item => item.type === 'tree' && item.path.startsWith(CONFIG.rutaBase + '/'))
                .map(item => {
                    const pathParts = item.path.split('/');
                    return pathParts[1]; // Segundo nivel después de DocumentosClientes
                })
                .filter((cliente, index, self) => self.indexOf(cliente) === index); // Eliminar duplicados

            clientesExistentes = carpetas;
            
            // Llenar select con clientes existentes
            carpetas.forEach(cliente => {
                const option = document.createElement('option');
                option.value = cliente;
                option.textContent = cliente;
                selectCliente.appendChild(option);
            });
        } catch (error) {
            console.error('Error cargando clientes:', error);
        }
    }

    function prevenirComportamiento(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function manejarDrop(e) {
        const dt = e.dataTransfer;
        const archivos = dt.files;
        procesarArchivos(archivos);
    }

    function manejarSeleccionArchivos(e) {
        const archivos = e.target.files;
        procesarArchivos(archivos);
    }

    function procesarArchivos(archivos) {
        if (archivos.length === 0) return;

        // Verificar token antes de procesar
        if (!CONFIG.token || CONFIG.token === "ghp_tu_token_aqui") {
            alert('Token de GitHub no configurado. No se pueden subir archivos.');
            return;
        }

        // Convertir FileList a Array y agregar a archivos seleccionados
        const nuevosArchivos = Array.from(archivos);
        
        // Verificar duplicados
        nuevosArchivos.forEach(archivo => {
            const existe = archivosSeleccionados.some(a => a.name === archivo.name && a.size === archivo.size);
            if (!existe) {
                archivosSeleccionados.push(archivo);
            }
        });

        actualizarListaArchivos();
        validarFormulario();
    }

    function actualizarListaArchivos() {
        archivosContainer.innerHTML = '';
        
        archivosSeleccionados.forEach((archivo, index) => {
            const div = document.createElement('div');
            div.className = 'flex items-center justify-between p-3 bg-gray-50 rounded-lg';
            div.innerHTML = `
                <div class="flex items-center">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-gray-500 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <div>
                        <p class="text-sm font-medium text-gray-700">${archivo.name}</p>
                        <p class="text-xs text-gray-500">${formatearTamaño(archivo.size)}</p>
                    </div>
                </div>
                <button type="button" class="text-red-600 hover:text-red-800" data-index="${index}">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                </button>
            `;
            archivosContainer.appendChild(div);
        });

        // Agregar event listeners a botones de eliminar
        archivosContainer.querySelectorAll('button').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const index = parseInt(e.currentTarget.getAttribute('data-index'));
                archivosSeleccionados.splice(index, 1);
                actualizarListaArchivos();
                validarFormulario();
            });
        });

        // Mostrar/ocultar lista
        if (archivosSeleccionados.length > 0) {
            listaArchivos.classList.remove('hidden');
        } else {
            listaArchivos.classList.add('hidden');
        }
    }

    function validarFormulario() {
        const clienteSeleccionado = selectCliente.value;
        const nuevoClienteValor = nuevoCliente.value.trim();
        const hayArchivos = archivosSeleccionados.length > 0;
        const hayCliente = clienteSeleccionado || nuevoClienteValor;
        const tokenConfigurado = CONFIG.token && CONFIG.token !== "ghp_tu_token_aqui";

        btnSubir.disabled = !(hayArchivos && hayCliente && tokenConfigurado);
    }

    function formatearTamaño(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    async function subirArchivos() {
        if (!CONFIG.token || CONFIG.token === "ghp_tu_token_aqui") {
            alert('Token de GitHub no configurado. Por favor, configura el token en config.js');
            return;
        }

        // Obtener información del cliente y ruta
        const cliente = selectCliente.value || nuevoCliente.value.trim();
        const ruta = rutaCliente.value.trim();
        
        if (!cliente) {
            alert('Por favor, selecciona o ingresa un nombre de cliente.');
            return;
        }

        // Preparar interfaz para subida
        prepararInterfazSubida();

        // Subir archivos uno por uno
        let exitosos = 0;
        let fallidos = 0;

        for (let i = 0; i < archivosSeleccionados.length; i++) {
            const archivo = archivosSeleccionados[i];
            const resultado = await subirArchivo(archivo, cliente, ruta, i);
            
            if (resultado.exito) {
                exitosos++;
                actualizarProgresoArchivo(i, 'completado', resultado.url);
            } else {
                fallidos++;
                actualizarProgresoArchivo(i, 'error', resultado.mensaje);
            }

            // Actualizar progreso global
            const progreso = ((i + 1) / archivosSeleccionados.length) * 100;
            barraProgresoGlobal.style.width = `${progreso}%`;
        }

        // Mostrar resultados finales
        mostrarResultados(exitosos, fallidos);
    }

    function prepararInterfazSubida() {
        // Deshabilitar controles
        btnSubir.disabled = true;
        btnCancelar.disabled = true;
        fileInput.disabled = true;
        btnSeleccionar.disabled = true;
        selectCliente.disabled = true;
        nuevoCliente.disabled = true;
        rutaCliente.disabled = true;

        // Mostrar contenedor de progreso
        progresoContainer.classList.remove('hidden');
        barraProgresoGlobal.style.width = '0%';
        detalleProgreso.innerHTML = '';

        // Crear elementos de progreso para cada archivo
        archivosSeleccionados.forEach((archivo, index) => {
            const div = document.createElement('div');
            div.className = 'flex items-center justify-between p-3 bg-gray-50 rounded-lg';
            div.id = `progreso-${index}`;
            div.innerHTML = `
                <div class="flex items-center">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-gray-500 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <div>
                        <p class="text-sm font-medium text-gray-700">${archivo.name}</p>
                        <p class="text-xs text-gray-500">${formatearTamaño(archivo.size)}</p>
                    </div>
                </div>
                <div class="flex items-center">
                    <div class="w-24 bg-gray-200 rounded-full h-2 mr-3">
                        <div id="barra-${index}" class="bg-red-600 h-2 rounded-full" style="width: 0%"></div>
                    </div>
                    <span id="estado-${index}" class="text-xs font-medium">Esperando...</span>
                </div>
            `;
            detalleProgreso.appendChild(div);
        });
    }

    async function subirArchivo(archivo, cliente, ruta, index) {
        try {
            // Actualizar estado del archivo
            actualizarProgresoArchivo(index, 'subiendo');

            // Construir ruta completa
            let rutaCompleta = `${CONFIG.rutaBase}/${cliente}`;
            if (ruta) {
                rutaCompleta += `/${ruta}`;
            }
            rutaCompleta += `/${archivo.name}`;

            // Leer archivo como base64
            const contenidoBase64 = await leerArchivoComoBase64(archivo);

            // Crear el contenido para la API de GitHub
            const contenido = {
                message: `Subir archivo: ${archivo.name}`,
                content: contenidoBase64.split(',')[1] // Remover el prefijo data:*/*;base64,
            };

            // Hacer la petición a la API de GitHub
            const url = `https://api.github.com/repos/${CONFIG.usuario}/${CONFIG.repositorio}/contents/${rutaCompleta}`;
            
            const respuesta = await fetch(url, {
                method: 'PUT',
                headers: {
                    'Authorization': `token ${CONFIG.token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(contenido)
            });

            if (!respuesta.ok) {
                const errorData = await respuesta.json();
                throw new Error(errorData.message || 'Error al subir archivo');
            }

            const data = await respuesta.json();
            
            return {
                exito: true,
                url: data.content.html_url
            };

        } catch (error) {
            console.error('Error subiendo archivo:', error);
            return {
                exito: false,
                mensaje: error.message
            };
        }
    }

    function leerArchivoComoBase64(archivo) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = error => reject(error);
            reader.readAsDataURL(archivo);
        });
    }

    function actualizarProgresoArchivo(index, estado, informacionAdicional = '') {
        const barra = document.getElementById(`barra-${index}`);
        const estadoElemento = document.getElementById(`estado-${index}`);
        const elementoProgreso = document.getElementById(`progreso-${index}`);

        if (!barra || !estadoElemento) return;

        switch (estado) {
            case 'subiendo':
                barra.style.width = '50%';
                estadoElemento.textContent = 'Subiendo...';
                estadoElemento.className = 'text-xs font-medium text-yellow-600';
                break;
            case 'completado':
                barra.style.width = '100%';
                estadoElemento.textContent = 'Completado';
                estadoElemento.className = 'text-xs font-medium text-green-600';
                
                // Agregar enlace al archivo si está disponible
                if (informacionAdicional) {
                    const enlace = document.createElement('a');
                    enlace.href = informacionAdicional;
                    enlace.target = '_blank';
                    enlace.className = 'ml-2 text-blue-600 hover:underline text-xs';
                    enlace.textContent = 'Ver archivo';
                    estadoElemento.appendChild(enlace);
                }
                break;
            case 'error':
                barra.style.width = '100%';
                barra.className = 'bg-red-600 h-2 rounded-full';
                estadoElemento.textContent = `Error: ${informacionAdicional}`;
                estadoElemento.className = 'text-xs font-medium text-red-600';
                elementoProgreso.classList.add('bg-red-50');
                break;
        }
    }

    function mostrarResultados(exitosos, fallidos) {
        resultadosContainer.classList.remove('hidden');
        resultados.innerHTML = '';

        if (exitosos > 0) {
            const divExito = document.createElement('div');
            divExito.className = 'p-4 bg-green-50 text-green-700 rounded-lg';
            divExito.innerHTML = `
                <div class="flex items-center">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                    </svg>
                    <span class="font-medium">${exitosos} archivo(s) subido(s) correctamente</span>
                </div>
            `;
            resultados.appendChild(divExito);
        }

        if (fallidos > 0) {
            const divError = document.createElement('div');
            divError.className = 'p-4 bg-red-50 text-red-700 rounded-lg mt-3';
            divError.innerHTML = `
                <div class="flex items-center">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                    <span class="font-medium">${fallidos} archivo(s) fallaron al subir</span>
                </div>
            `;
            resultados.appendChild(divError);
        }

        // Habilitar botón para nueva subida
        const btnNuevaSubida = document.createElement('button');
        btnNuevaSubida.className = 'mt-4 bg-red-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-red-700 transition';
        btnNuevaSubida.textContent = 'Subir más archivos';
        btnNuevaSubida.addEventListener('click', () => {
            location.reload();
        });
        resultados.appendChild(btnNuevaSubida);
    }

    function cancelarSubida() {
        if (confirm('¿Estás seguro de que quieres cancelar? Se perderán los archivos seleccionados.')) {
            archivosSeleccionados = [];
            actualizarListaArchivos();
            validarFormulario();
        }
    }
});