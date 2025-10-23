// Script para el reporte completo
document.addEventListener('DOMContentLoaded', function() {
    const loader = document.getElementById('loader');
    const tablaReporte = document.getElementById('tablaReporte');
    const tbodyReporte = document.getElementById('tbodyReporte');
    const sinResultados = document.getElementById('sinResultados');
    const buscarInput = document.getElementById('buscarInput');
    const btnExportar = document.getElementById('btnExportar');
    const totalArchivos = document.getElementById('totalArchivos');
    const totalClientes = document.getElementById('totalClientes');

    let todosLosArchivos = [];
    let datosFiltrados = [];
    let sortColumn = 'cliente';
    let sortDirection = 'asc';

    // Cargar datos
    cargarReporteCompleto();

    // Event listeners
    buscarInput.addEventListener('input', filtrarDatos);
    btnExportar.addEventListener('click', exportarCSV);
    
    // Ordenar columnas
    document.querySelectorAll('th[data-sort]').forEach(th => {
        th.addEventListener('click', () => {
            const column = th.getAttribute('data-sort');
            if (sortColumn === column) {
                sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                sortColumn = column;
                sortDirection = 'asc';
            }
            ordenarDatos();
            renderizarTabla();
            actualizarIconosOrden();
        });
    });

    async function cargarReporteCompleto() {
        try {
            loader.classList.remove('hidden');
            tablaReporte.classList.add('hidden');
            sinResultados.classList.add('hidden');

            const resp = await fetch(CONFIG.baseURL);
            const data = await resp.json();
            
            if (!data.tree) throw new Error("No se encontró contenido");

            // Filtrar solo archivos (no carpetas) que estén dentro de DocumentosClientes
            todosLosArchivos = data.tree
                .filter(item => item.type === 'blob' && item.path.startsWith(CONFIG.rutaBase + '/'))
                .map(item => {
                    const pathParts = item.path.split('/');
                    const cliente = pathParts[1]; // Segundo nivel después de DocumentosClientes
                    const nombreArchivo = pathParts[pathParts.length - 1];
                    const extension = nombreArchivo.split('.').pop().toLowerCase();
                    const url = `https://raw.githubusercontent.com/${CONFIG.usuario}/${CONFIG.repositorio}/main/${encodeURIComponent(item.path).replace(/%2F/g, "/")}`;
                    
                    return {
                        cliente: cliente,
                        ruta: item.path,
                        nombre: nombreArchivo,
                        extension: extension,
                        url: url,
                        tipo: obtenerTipoArchivo(extension)
                    };
                });

            datosFiltrados = [...todosLosArchivos];
            actualizarEstadisticas();
            ordenarDatos();
            renderizarTabla();
            
            loader.classList.add('hidden');
            tablaReporte.classList.remove('hidden');

        } catch (error) {
            console.error('Error cargando reporte:', error);
            loader.classList.add('hidden');
            sinResultados.classList.remove('hidden');
            sinResultados.innerHTML = '<p class="text-red-600 text-lg">Error al cargar el reporte</p>';
        }
    }

    function obtenerTipoArchivo(extension) {
        const tipos = {
            pdf: 'PDF',
            xlsx: 'Excel',
            xls: 'Excel',
            doc: 'Word',
            docx: 'Word',
            ppt: 'PowerPoint',
            pptx: 'PowerPoint',
            png: 'Imagen',
            jpg: 'Imagen',
            jpeg: 'Imagen',
            gif: 'Imagen',
            bmp: 'Imagen',
            svg: 'Imagen',
            txt: 'Texto',
            csv: 'CSV'
        };
        return tipos[extension] || 'Otro';
    }

    function actualizarEstadisticas() {
        totalArchivos.textContent = todosLosArchivos.length;
        
        const clientesUnicos = new Set(todosLosArchivos.map(archivo => archivo.cliente));
        totalClientes.textContent = clientesUnicos.size;
    }

    function ordenarDatos() {
        datosFiltrados.sort((a, b) => {
            let valueA = a[sortColumn];
            let valueB = b[sortColumn];
            
            if (sortColumn === 'cliente' || sortColumn === 'nombre' || sortColumn === 'extension' || sortColumn === 'tipo') {
                valueA = valueA.toLowerCase();
                valueB = valueB.toLowerCase();
            }
            
            if (valueA < valueB) return sortDirection === 'asc' ? -1 : 1;
            if (valueA > valueB) return sortDirection === 'asc' ? 1 : -1;
            return 0;
        });
    }

    function actualizarIconosOrden() {
        document.querySelectorAll('th[data-sort]').forEach(th => {
            const column = th.getAttribute('data-sort');
            let icon = 'ↂ';
            if (column === sortColumn) {
                icon = sortDirection === 'asc' ? '↑' : '↓';
            }
            th.innerHTML = th.textContent.replace(/[ↂ↑↓]/g, '') + ' ' + icon;
        });
    }

    function renderizarTabla() {
        tbodyReporte.innerHTML = '';
        
        if (datosFiltrados.length === 0) {
            tablaReporte.classList.add('hidden');
            sinResultados.classList.remove('hidden');
            return;
        }

        tablaReporte.classList.remove('hidden');
        sinResultados.classList.add('hidden');

        datosFiltrados.forEach(archivo => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-gray-50';
            tr.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    ${archivo.cliente}
                </td>
                <td class="px-6 py-4 text-sm text-gray-500">
                    <div class="max-w-xs truncate" title="${archivo.ruta}">
                        ${archivo.ruta}
                    </div>
                </td>
                <td class="px-6 py-4 text-sm text-gray-900">
                    ${archivo.nombre}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                        ${archivo.extension.toUpperCase()}
                    </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    <a href="${archivo.url}" target="_blank" class="text-red-600 hover:text-red-900 underline truncate block max-w-xs">
                        Ver archivo
                    </a>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        ${archivo.tipo}
                    </span>
                </td>
            `;
            tbodyReporte.appendChild(tr);
        });
    }

    function filtrarDatos() {
        const termino = buscarInput.value.toLowerCase().trim();
        
        if (!termino) {
            datosFiltrados = [...todosLosArchivos];
        } else {
            datosFiltrados = todosLosArchivos.filter(archivo => 
                archivo.cliente.toLowerCase().includes(termino) ||
                archivo.ruta.toLowerCase().includes(termino) ||
                archivo.nombre.toLowerCase().includes(termino) ||
                archivo.extension.toLowerCase().includes(termino) ||
                archivo.tipo.toLowerCase().includes(termino)
            );
        }
        
        ordenarDatos();
        renderizarTabla();
    }

    function exportarCSV() {
        if (datosFiltrados.length === 0) return;

        const headers = ['Cliente', 'Ruta Completa', 'Nombre Archivo', 'Extensión', 'URL', 'Tipo'];
        const csvContent = [
            headers.join(','),
            ...datosFiltrados.map(archivo => [
                `"${archivo.cliente}"`,
                `"${archivo.ruta}"`,
                `"${archivo.nombre}"`,
                `"${archivo.extension}"`,
                `"${archivo.url}"`,
                `"${archivo.tipo}"`
            ].join(','))
        ].join('\n');

        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        
        link.setAttribute('href', url);
        link.setAttribute('download', `reporte_documentos_${new Date().toISOString().split('T')[0]}.csv`);
        link.style.visibility = 'hidden';
        
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
});