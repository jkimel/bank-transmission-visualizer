class DataTableManager {
    constructor() {
        this.currentPage = 1;
        this.pageSize = 25;
        this.currentSort = 'id';
        this.currentSortDir = 'asc';
        this.currentFilters = {};
        this.currentSearch = '';
        
        this.initializeEventListeners();
        this.loadTableData();
        this.loadFilterOptions();
        this.loadDataInfo();
    }

    // Añadir estos métodos a la clase DataTableManager

async loadFilterOptions() {
    try {
        const response = await fetch('/api/filter-options');
        const options = await response.json();
        
        // Llenar dropdowns de filtros
        this.populateFilter('entityFilter', options.entities || []);
        this.populateFilter('systemFilter', options.systems || []);
        this.populateFilter('typeFilter', options.types || []);
    } catch (error) {
        console.error('Error loading filter options:', error);
    }
}

populateFilter(selectId, options) {
    const select = document.getElementById(selectId);
    if (!select) return;
    
    // Mantener la opción "Todos"
    const currentValue = select.value;
    select.innerHTML = '<option value="">Todos</option>';
    
    options.forEach(option => {
        const optionElement = document.createElement('option');
        optionElement.value = option;
        optionElement.textContent = option;
        select.appendChild(optionElement);
    });
    
    // Restaurar selección si existe
    if (options.includes(currentValue)) {
        select.value = currentValue;
    }
}

applyFilters() {
    this.currentFilters = {
        entity: document.getElementById('entityFilter').value,
        system: document.getElementById('systemFilter').value,
        type: document.getElementById('typeFilter').value,
        risk: document.getElementById('riskFilter').value
    };
    this.currentPage = 1;
    this.loadTableData();
}

resetFilters() {
    document.getElementById('entityFilter').value = '';
    document.getElementById('systemFilter').value = '';
    document.getElementById('typeFilter').value = '';
    document.getElementById('riskFilter').value = '';
    this.currentSearch = '';
    document.getElementById('searchInput').value = '';
    this.currentFilters = {};
    this.currentPage = 1;
    this.loadTableData();
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
    this.updateSortIcons();
}

updateSortIcons() {
    document.querySelectorAll('th[data-sort] i').forEach(icon => {
        icon.className = 'fas fa-sort ms-1';
    });
    
    const currentTh = document.querySelector(`th[data-sort="${this.currentSort}"]`);
    if (currentTh) {
        const icon = currentTh.querySelector('i');
        if (icon) {
            icon.className = this.currentSortDir === 'asc' 
                ? 'fas fa-sort-up ms-1' 
                : 'fas fa-sort-down ms-1';
        }
    }
}

renderPagination(result) {
    const pagination = document.getElementById('pagination');
    if (!pagination) return;
    
    const totalPages = Math.ceil(result.total / this.pageSize);
    
    let html = '';
    
    // Botón anterior
    html += `<li class="page-item ${this.currentPage === 1 ? 'disabled' : ''}">
        <a class="page-link" href="#" data-page="${this.currentPage - 1}">Anterior</a>
    </li>`;
    
    // Páginas
    for (let i = 1; i <= totalPages; i++) {
        html += `<li class="page-item ${i === this.currentPage ? 'active' : ''}">
            <a class="page-link" href="#" data-page="${i}">${i}</a>
        </li>`;
    }
    
    // Botón siguiente
    html += `<li class="page-item ${this.currentPage === totalPages ? 'disabled' : ''}">
        <a class="page-link" href="#" data-page="${this.currentPage + 1}">Siguiente</a>
    </li>`;
    
    pagination.innerHTML = html;
    
    // Event listeners para paginación
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
    
    if (showingFrom && showingTo && totalRows) {
        const from = (this.currentPage - 1) * this.pageSize + 1;
        const to = Math.min(this.currentPage * this.pageSize, result.total);
        
        showingFrom.textContent = from;
        showingTo.textContent = to;
        totalRows.textContent = result.total;
    }
}

debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

showError(message) {
    console.error(message);
    // Puedes implementar notificaciones toast aquí
    alert(message); // Temporal
}

initializeEventListeners() {
        // Pagination
        document.getElementById('pageSize').addEventListener('change', (e) => {
            this.pageSize = parseInt(e.target.value);
            this.currentPage = 1;
            this.loadTableData();
        });

        // Search
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.addEventListener('input', this.debounce((e) => {
                this.currentSearch = e.target.value;
                this.currentPage = 1;
                this.loadTableData();
            }, 300));
        }

        // Filters
        const applyFiltersBtn = document.getElementById('applyFilters');
        if (applyFiltersBtn) {
            applyFiltersBtn.addEventListener('click', () => this.applyFilters());
        }

        const resetFiltersBtn = document.getElementById('resetFilters');
        if (resetFiltersBtn) {
            resetFiltersBtn.addEventListener('click', () => this.resetFilters());
        }

        // Sort headers
        document.querySelectorAll('th[data-sort]').forEach(th => {
            th.addEventListener('click', () => this.handleSort(th.dataset.sort));
        });
    }

    async loadTableData() {
        const params = new URLSearchParams({
            page: this.currentPage,
            size: this.pageSize,
            sort: this.currentSort,
            sort_dir: this.currentSortDir,
            search: this.currentSearch
        });

        // Add filters
        Object.entries(this.currentFilters).forEach(([key, value]) => {
            if (value) params.append(key, value);
        });

        try {
            console.log('Cargando datos de la tabla...');
            const response = await fetch(`/api/table?${params}`);
            const result = await response.json();

            if (response.ok) {
                console.log('Datos recibidos:', result);
                this.renderTable(result.data);
                this.renderPagination(result);
                this.updateTableInfo(result);
            } else {
                this.showError('Error cargando datos: ' + (result.error || 'Error desconocido'));
            }
        } catch (error) {
            console.error('Error:', error);
            this.showError('Error de conexión: ' + error.message);
        }
    }

    
    renderTable(data) {
        const tbody = document.getElementById('tableBody');
        
        if (!tbody) {
            console.error('No se encontró el elemento tableBody');
            return;
        }

        if (!data || data.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center py-4 text-muted">
                        <i class="fas fa-inbox fa-2x mb-3"></i><br>
                        No se encontraron registros<br>
                        <small class="text-muted">Intenta ajustar los filtros o subir un archivo CSV</small>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = '';

        data.forEach(row => {
            const tr = document.createElement('tr');
            tr.style.cursor = 'pointer';
            
            // Función helper para manejar valores vacíos o nulos
            const getSafeValue = (value, defaultValue = '-') => {
                if (value === null || value === undefined || value === '' || value === 'No especificado') {
                    return `<span class="text-muted fst-italic">${defaultValue}</span>`;
                }
                return this.escapeHtml(value.toString());
            };

            // Función helper para determinar clase de riesgo
            const getRiskClass = (riesgo) => {
                if (!riesgo || riesgo === 'No especificado') return 'risk-unknown';
                return `risk-${riesgo.toLowerCase()}`;
            };

            // Función helper para texto de riesgo
            const getRiskText = (riesgo) => {
                if (!riesgo || riesgo === 'No especificado') return 'No especificado';
                return riesgo;
            };

            tr.innerHTML = `
                <td class="fw-bold">${row.id}</td>
                <td>${getSafeValue(row.Entidad, 'Entidad no especificada')}</td>
                <td>${getSafeValue(row['Sistema de origen'], 'Sistema origen no especificado')}</td>
                <td>${getSafeValue(row['Sistema de Destino'], 'Sistema destino no especificado')}</td>
                <td>
                    <span class="badge bg-light text-dark border">
                        ${getSafeValue(row['Tipo de Transmisión'], 'Tipo no especificado')}
                    </span>
                </td>
                <td>${getSafeValue(row['Propietario Datos de Destino'], 'Propietario no especificado')}</td>
                <td>
                    <span class="risk-badge ${getRiskClass(row['Riesgo de falla'])}">
                        ${getRiskText(row['Riesgo de falla'])}
                    </span>
                </td>
            `;

            tr.addEventListener('click', () => {
                if (row.id) {
                    window.location.href = `/graph?row_id=${row.id}`;
                }
            });

            tr.addEventListener('mouseenter', () => {
                tr.style.backgroundColor = '#f8f9fa';
            });

            tr.addEventListener('mouseleave', () => {
                tr.style.backgroundColor = '';
            });

            tbody.appendChild(tr);
        });
    }

    async loadDataInfo() {
        try {
            const response = await fetch('/api/data-info');
            const text = await response.text();
            const info = JSON.parse(text);

            if (info.loaded) {
                this.updateDataInfoPanel(info);
            }
        } catch (error) {
            console.error('Error loading data info:', error);
        }
    }

    updateDataInfoPanel(info) {
        // Actualizar panel de información si existe
        const infoPanel = document.getElementById('dataInfoPanel');
        if (!infoPanel) return;

        let infoHTML = `
            <div class="row small">
                <div class="col-md-6">
                    <strong>Archivo:</strong> ${info.filename}<br>
                    <strong>Filas:</strong> ${info.total_rows}<br>
                    <strong>Columnas:</strong> ${info.total_columns}
                </div>
                <div class="col-md-6">
        `;

        // Mostrar estadísticas de campos vacíos
        if (info.empty_stats) {
            const columnsWithEmpty = Object.entries(info.empty_stats)
                .filter(([col, stats]) => stats.empty_count > 0)
                .slice(0, 3); // Mostrar solo las primeras 3 columnas con datos vacíos

            if (columnsWithEmpty.length > 0) {
                infoHTML += `<strong>Campos con valores vacíos:</strong><br>`;
                columnsWithEmpty.forEach(([col, stats]) => {
                    infoHTML += `• ${col}: ${stats.empty_count} (${stats.empty_percentage}%)<br>`;
                });
            }
        }

        infoHTML += `</div></div>`;
        infoPanel.innerHTML = infoHTML;
    }
}

// Inicializar cuando la página cargue
document.addEventListener('DOMContentLoaded', function() {
    console.log('Inicializando DataTableManager...');
    
    if (document.getElementById('tableBody')) {
        window.tableManager = new DataTableManager();
        console.log('DataTableManager inicializado');
    }
    
    const downloadBtn = document.getElementById('downloadBtn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', function() {
            window.location.href = '/api/download';
        });
    }
});