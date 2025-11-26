class DataTableManager {
    constructor() {
        this.currentPage = 1;
        this.pageSize = 25;
        this.currentSort = 'id';
        this.currentSortDir = 'asc';
        this.currentSearch = '';
        
        // Estado de los filtros específicos
        this.filters = {
            origen: '',
            destino: ''
        };
        
        this.initializeEventListeners();
        this.loadFilterOptions(); // <--- Recuperamos esta función
        this.loadTableData();
        this.loadDataInfo();
    }

    initializeEventListeners() {
        // Paginación
        document.getElementById('pageSize').addEventListener('change', (e) => {
            this.pageSize = parseInt(e.target.value);
            this.currentPage = 1;
            this.loadTableData();
        });

        // Búsqueda General (al escribir)
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.addEventListener('input', this.debounce((e) => {
                this.currentSearch = e.target.value;
                this.currentPage = 1;
                this.loadTableData();
            }, 300));
        }

        // Botón APLICAR (Ahora sí tiene sentido: aplica los dropdowns)
        const applyFiltersBtn = document.getElementById('applyFilters');
        if (applyFiltersBtn) {
            applyFiltersBtn.addEventListener('click', () => {
                // Leer valores de los dropdowns
                this.filters.origen = document.getElementById('filterOrigen').value;
                this.filters.destino = document.getElementById('filterDestino').value;
                
                this.currentPage = 1;
                this.loadTableData();
            });
        }

        // Botón RESETEAR
        const resetFiltersBtn = document.getElementById('resetFilters');
        if (resetFiltersBtn) {
            resetFiltersBtn.addEventListener('click', () => this.resetFilters());
        }

        // Ordenar columnas
        document.addEventListener('click', (e) => {
            if (e.target.closest('th[data-sort]')) {
                const th = e.target.closest('th[data-sort]');
                this.handleSort(th.dataset.sort);
            }
        });
    }

    async loadFilterOptions() {
        try {
            // Usamos ruta relativa
            const response = await fetch('/api/filter-options');
            const data = await response.json();

            if (data.origenes && data.destinos) {
                this.populateSelect('filterOrigen', data.origenes);
                this.populateSelect('filterDestino', data.destinos);
            }
        } catch (error) {
            console.error('Error cargando opciones de filtro:', error);
        }
    }

    populateSelect(elementId, options) {
        const select = document.getElementById(elementId);
        if (!select) return;
        
        // Guardar selección actual si existe
        const currentValue = select.value;
        
        // Limpiar (mantener la primera opción "Todos")
        select.innerHTML = '<option value="">Todos</option>';
        
        // Ordenar alfabéticamente numérico (R1, R2, R10...)
        options.sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));

        options.forEach(opt => {
            const option = document.createElement('option');
            option.value = opt;
            option.textContent = opt;
            select.appendChild(option);
        });

        // Restaurar valor si aun existe
        if (options.includes(currentValue)) {
            select.value = currentValue;
        }
    }

    async loadTableData() {
        const params = new URLSearchParams({
            page: this.currentPage,
            size: this.pageSize,
            sort: this.currentSort,
            sort_dir: this.currentSortDir,
            search: this.currentSearch,
            // Enviamos los filtros al backend
            origen: this.filters.origen,
            destino: this.filters.destino
        });

        try {
            // Ruta relativa
            // const response = await fetch(`/api/table?${params}`);
            const response = await fetch(`https://bank-transmission-visualizer.onrender.com/api/table?${params}`);
            // para render
            const result = await response.json();

            if (response.ok) {
                this.renderTable(result.data);
                this.renderPagination(result);
                this.updateTableInfo(result);
                this.updateSortIcons();
            } else {
                console.error('Error cargando datos:', result.error);
            }
        } catch (error) {
            console.error('Error de conexión:', error);
        }
    }

    resetFilters() {
        // Limpiar variables
        this.currentSearch = '';
        this.filters.origen = '';
        this.filters.destino = '';

        // Limpiar inputs visuales
        document.getElementById('searchInput').value = '';
        document.getElementById('filterOrigen').value = '';
        document.getElementById('filterDestino').value = '';

        this.currentPage = 1;
        this.loadTableData();
    }

    // --- (El resto de métodos de renderizado se mantienen igual, pero los incluyo para completar) ---
    renderTable(data) {
        const tbody = document.getElementById('tableBody');
        if (!tbody) return;

        if (!data || data.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="4" class="text-center py-5 text-muted">
                        <i class="fas fa-inbox fa-2x mb-3 text-light-gray"></i><br>
                        No se encontraron registros
                    </td>
                </tr>`;
            return;
        }

        tbody.innerHTML = '';
        data.forEach(row => {
            const tr = document.createElement('tr');
            
            // Renderizado condicional de latencia (colores)
            let latencyColor = 'text-dark';
            const lat = parseFloat(row.Latencia_ms);
            if (lat < 15) latencyColor = 'text-success fw-bold';
            else if (lat > 40) latencyColor = 'text-danger fw-bold';
            else latencyColor = 'text-warning fw-bold';

            tr.innerHTML = `
                <td><span class="badge bg-light text-dark border">${row.id}</span></td>
                <td>${row.Origen}</td>
                <td>${row.Destino}</td>
                <td class="${latencyColor}">${lat.toFixed(2)} ms</td>
            `;
            tbody.appendChild(tr);
        });
    }

    handleSort(column) {
        if (this.currentSort === column) {
            this.currentSortDir = this.currentSortDir === 'asc' ? 'desc' : 'asc';
        } else {
            this.currentSort = column;
            this.currentSortDir = 'asc';
        }
        this.currentPage = 1;
        this.loadTableData();
    }

    updateSortIcons() {
        document.querySelectorAll('th[data-sort] i').forEach(icon => {
            icon.className = 'fas fa-sort ms-1 text-muted'; // Reset
        });
        const currentTh = document.querySelector(`th[data-sort="${this.currentSort}"]`);
        if (currentTh) {
            const icon = currentTh.querySelector('i');
            icon.className = this.currentSortDir === 'asc' ? 'fas fa-sort-up ms-1 text-dark' : 'fas fa-sort-down ms-1 text-dark';
        }
    }

    renderPagination(result) {
        const pagination = document.getElementById('pagination');
        if (!pagination) return;
        
        const totalPages = result.total_pages || 1;
        let html = '';
        
        // Anterior
        html += `<li class="page-item ${this.currentPage === 1 ? 'disabled' : ''}">
            <a class="page-link" href="#" data-page="${this.currentPage - 1}">&laquo;</a>
        </li>`;
        
        // Rango de páginas (máximo 5 visibles)
        let startPage = Math.max(1, this.currentPage - 2);
        let endPage = Math.min(totalPages, this.currentPage + 2);

        if (this.currentPage <= 3) endPage = Math.min(5, totalPages);
        if (this.currentPage > totalPages - 2) startPage = Math.max(1, totalPages - 4);
        
        for (let i = startPage; i <= endPage; i++) {
            html += `<li class="page-item ${i === this.currentPage ? 'active' : ''}">
                <a class="page-link" href="#" data-page="${i}">${i}</a>
            </li>`;
        }
        
        // Siguiente
        html += `<li class="page-item ${this.currentPage === totalPages ? 'disabled' : ''}">
            <a class="page-link" href="#" data-page="${this.currentPage + 1}">&raquo;</a>
        </li>`;
        
        pagination.innerHTML = html;
        
        pagination.querySelectorAll('.page-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const page = parseInt(link.dataset.page);
                if (page >= 1 && page <= totalPages && page !== this.currentPage) {
                    this.currentPage = page;
                    this.loadTableData();
                }
            });
        });
    }

    updateTableInfo(result) {
        const showingFrom = document.getElementById('showingFrom');
        const showingTo = document.getElementById('showingTo');
        const totalRows = document.getElementById('totalRows');
        
        if (showingFrom) {
            const from = (this.currentPage - 1) * this.pageSize + 1;
            const to = Math.min(this.currentPage * this.pageSize, result.total);
            
            showingFrom.textContent = result.total === 0 ? 0 : from;
            showingTo.textContent = to;
            totalRows.textContent = result.total;
        }
    }

    async loadDataInfo() {
        // Carga info extra del archivo (opcional)
        try {
            const response = await fetch('/api/data-info');
            const info = await response.json();
            const panel = document.getElementById('dataInfoPanel');
            if (panel && info.loaded) {
                panel.innerHTML = `<small>Archivo: <strong>${info.filename}</strong> | Total Registros: ${info.total_rows}</small>`;
                panel.classList.remove('d-none');
            }
        } catch (e) { console.error(e); }
    }

    debounce(func, wait) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }
}

document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('tableBody')) {
        window.tableManager = new DataTableManager();
    }
});