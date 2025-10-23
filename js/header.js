// Cargar header
document.getElementById('header').innerHTML = `
  <header class="brand-red text-white shadow-md">
    <div class="max-w-6xl mx-auto px-6 py-6 flex flex-col sm:flex-row justify-between items-center">
      <div class="flex items-center space-x-4">
        <img src="https://www.visionymarketing.com.co/assets/images/v3/logo-vision-marketing-ohla-blanco.png"
             alt="Logo Visión y Marketing" class="h-10">
        <h1 class="text-2xl font-bold tracking-wide">Portal de Documentos de Clientes</h1>
      </div>
      <nav class="mt-4 sm:mt-0 flex space-x-4">
        <a href="index.html" class="bg-white text-red-600 px-4 py-2 rounded-lg font-semibold hover:bg-gray-100 transition">
          Explorador
        </a>
        <a href="reporte.html" class="bg-white text-red-600 px-4 py-2 rounded-lg font-semibold hover:bg-gray-100 transition">
          Reporte Completo
        </a>
      </nav>
    </div>
  </header>
`;