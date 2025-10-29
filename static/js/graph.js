class GraphManager {
    constructor() {
        this.network = null;
        this.nodes = new vis.DataSet();
        this.edges = new vis.DataSet();
        this.container = document.getElementById('network');
        this.currentRowId = this.getRowIdFromURL();
        
        this.init();
    }

    getRowIdFromURL() {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get('row_id');
    }

    async init() {
        if (!this.container) {
            console.error('Network container not found');
            return;
        }

        if (!this.currentRowId) {
            this.showError('No se especificó ID de fila');
            return;
        }

        await this.loadGraphData();
        this.initGraph();
        this.initEventListeners();
    }

    async loadGraphData() {
        try {
            const response = await fetch(`/api/graph?row_id=${this.currentRowId}`);
            const data = await response.json();

            if (response.ok) {
                this.renderGraph(data);
            } else {
                this.showError(data.error || 'Error cargando datos del grafo');
            }
        } catch (error) {
            this.showError('Error de conexión: ' + error.message);
        }
    }

    renderGraph(data) {
        // Limpiar datos anteriores
        this.nodes.clear();
        this.edges.clear();

        // Crear nodos
        data.nodes.forEach(node => {
            this.nodes.add({
                id: node.id,
                label: node.label,
                title: node.title || node.label,
                color: this.getNodeColor(node.type),
                font: { size: 16, face: 'Inter, sans-serif' },
                shape: 'box',
                margin: 15,
                widthConstraint: {
                    minimum: 100,
                    maximum: 200
                },
                shadow: {
                    enabled: true,
                    color: 'rgba(0,0,0,0.2)',
                    size: 10,
                    x: 5,
                    y: 5
                }
            });
        });

        // Crear conexiones
        data.edges.forEach(edge => {
            this.edges.add({
                from: edge.from,
                to: edge.to,
                label: edge.label,
                title: edge.title,
                arrows: 'to',
                color: {
                    color: '#666',
                    highlight: '#007bff',
                    hover: '#007bff'
                },
                font: { 
                    size: 12, 
                    face: 'Inter, sans-serif',
                    strokeWidth: 2,
                    strokeColor: 'white'
                },
                smooth: {
                    type: 'cubicBezier',
                    forceDirection: 'vertical'
                },
                shadow: {
                    enabled: true,
                    color: 'rgba(0,0,0,0.1)',
                    size: 5
                }
            });
        });
    }

    getNodeColor(nodeType) {
        const colors = {
            'origen': {
                background: '#667eea',
                border: '#5a6fd8',
                highlight: '#764ba2'
            },
            'destino': {
                background: '#f093fb',
                border: '#e184f0',
                highlight: '#f5576c'
            },
            'procesamiento': {
                background: '#4ecdc4',
                border: '#45b8b0',
                highlight: '#44a08d'
            },
            'default': {
                background: '#6c757d',
                border: '#5a6268',
                highlight: '#545b62'
            }
        };

        return colors[nodeType?.toLowerCase()] || colors.default;
    }

    initGraph() {
        const data = {
            nodes: this.nodes,
            edges: this.edges
        };

        const options = {
            layout: {
                hierarchical: {
                    enabled: true,
                    direction: 'UD', // Up-Down (de arriba hacia abajo)
                    sortMethod: 'directed',
                    levelSeparation: 200,
                    nodeSpacing: 150,
                    treeSpacing: 200,
                    blockShifting: true,
                    edgeMinimization: true,
                    parentCentralization: true
                }
            },
            physics: {
                enabled: false, // Desactiva la física para layout fijo
                stabilization: { iterations: 1000 }
            },
            interaction: {
                dragNodes: true,
                dragView: true,
                zoomView: true,
                hover: true,
                hoverConnectedEdges: true,
                selectable: true,
                selectConnectedEdges: true
            },
            nodes: {
                shape: 'box',
                margin: 15,
                widthConstraint: {
                    minimum: 120,
                    maximum: 250
                },
                font: {
                    size: 16,
                    face: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif',
                    color: '#333',
                    strokeWidth: 2,
                    strokeColor: 'rgba(255,255,255,0.8)'
                },
                borderWidth: 2,
                shadow: {
                    enabled: true,
                    color: 'rgba(0,0,0,0.2)',
                    size: 8,
                    x: 4,
                    y: 4
                },
                chosen: {
                    node: function(values, id, selected, hovering) {
                        values.shadow = true;
                        values.shadowColor = 'rgba(0,123,255,0.5)';
                        values.shadowSize = 15;
                        values.shadowX = 0;
                        values.shadowY = 0;
                    }
                }
            },
            edges: {
                arrows: {
                    to: {
                        enabled: true,
                        scaleFactor: 1.5,
                        type: 'arrow'
                    }
                },
                color: {
                    color: '#8492a6',
                    highlight: '#007bff',
                    hover: '#007bff',
                    opacity: 0.8
                },
                font: {
                    size: 12,
                    face: 'Inter, sans-serif',
                    align: 'middle',
                    color: '#666',
                    strokeWidth: 3,
                    strokeColor: 'rgba(255,255,255,0.8)'
                },
                smooth: {
                    type: 'cubicBezier',
                    forceDirection: 'vertical',
                    roundness: 0.4
                },
                shadow: {
                    enabled: true,
                    color: 'rgba(0,0,0,0.1)',
                    size: 3
                },
                width: 2,
                hoverWidth: 3,
                selectionWidth: 4
            },
            groups: {
                origen: {
                    color: '#667eea',
                    font: { color: 'white' }
                },
                destino: {
                    color: '#f093fb',
                    font: { color: 'white' }
                },
                procesamiento: {
                    color: '#4ecdc4',
                    font: { color: 'white' }
                }
            }
        };

        // Crear la red
        this.network = new vis.Network(this.container, data, options);

        // Configurar eventos de la red
        this.setupNetworkEvents();
    }

    setupNetworkEvents() {
        if (!this.network) return;

        // Evento al hacer hover en nodos
        this.network.on("hoverNode", (params) => {
            this.highlightConnectedElements(params.node);
        });

        // Evento al quitar hover
        this.network.on("blurNode", () => {
            this.resetHighlight();
        });

        // Evento al seleccionar nodo
        this.network.on("selectNode", (params) => {
            this.highlightConnectedElements(params.nodes[0]);
        });

        // Evento al deseleccionar
        this.network.on("deselectNode", () => {
            this.resetHighlight();
        });

        // Evento de doble click en nodo
        this.network.on("doubleClick", (params) => {
            if (params.nodes.length > 0) {
                this.zoomToNode(params.nodes[0]);
            }
        });
    }

    highlightConnectedElements(nodeId) {
        const connectedEdges = this.network.getConnectedEdges(nodeId);
        const connectedNodes = this.network.getConnectedNodes(nodeId);
        
        // Resetear todos los elementos primero
        this.resetHighlight();
        
        // Resaltar elementos conectados
        this.nodes.update(
            this.nodes.get().map(node => ({
                id: node.id,
                color: connectedNodes.includes(node.id) || node.id === nodeId ? 
                    this.getHighlightColor(node.color) : node.color,
                shadow: connectedNodes.includes(node.id) || node.id === nodeId
            }))
        );

        this.edges.update(
            this.edges.get().map(edge => ({
                id: edge.id,
                color: connectedEdges.includes(edge.id) ? 
                    { color: '#007bff', highlight: '#0056b3' } : edge.color,
                width: connectedEdges.includes(edge.id) ? 4 : 2
            }))
        );
    }

    getHighlightColor(originalColor) {
        if (typeof originalColor === 'object') {
            return {
                ...originalColor,
                background: this.lightenColor(originalColor.background, 20),
                border: this.lightenColor(originalColor.border, 20)
            };
        }
        return this.lightenColor(originalColor, 20);
    }

    lightenColor(color, percent) {
        // Implementación simple para aclarar colores
        return color; // Puedes implementar lógica más sofisticada aquí
    }

    resetHighlight() {
        // Restaurar colores originales de nodos
        const originalNodes = this.nodes.get().map(node => ({
            id: node.id,
            color: this.getNodeColorForReset(node.id),
            shadow: {
                enabled: true,
                color: 'rgba(0,0,0,0.2)',
                size: 8,
                x: 4,
                y: 4
            }
        }));
        this.nodes.update(originalNodes);

        // Restaurar bordes
        this.edges.update(
            this.edges.get().map(edge => ({
                id: edge.id,
                color: { color: '#8492a6', highlight: '#007bff' },
                width: 2
            }))
        );
    }

    getNodeColorForReset(nodeId) {
        // Lógica para determinar el color original del nodo
        // Esto debería basarse en tus datos reales
        return this.getNodeColor('default');
    }

    zoomToNode(nodeId) {
        const nodePosition = this.network.getPositions([nodeId])[nodeId];
        if (nodePosition) {
            this.network.focus(nodeId, {
                scale: 1.2,
                animation: {
                    duration: 1000,
                    easingFunction: 'easeInOutCubic'
                }
            });
        }
    }

    showError(message) {
        const errorDiv = document.getElementById('errorMessage');
        if (errorDiv) {
            errorDiv.innerHTML = `
                <div class="alert alert-danger alert-dismissible fade show" role="alert">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            `;
        } else {
            alert(message);
        }
    }

    // Métodos de utilidad
    exportAsImage() {
        if (this.network) {
            this.network.storePositions();
            const canvas = this.container.querySelector('canvas');
            if (canvas) {
                const link = document.createElement('a');
                link.download = `grafo-transmision-${this.currentRowId}.png`;
                link.href = canvas.toDataURL();
                link.click();
            }
        }
    }

    fitToScreen() {
        if (this.network) {
            this.network.fit({
                animation: {
                    duration: 1000,
                    easingFunction: 'easeInOutCubic'
                }
            });
        }
    }
}

// Inicializar cuando cargue la página
document.addEventListener('DOMContentLoaded', function() {
    window.graphManager = new GraphManager();
    
    // Event listeners para controles
    const exportBtn = document.getElementById('exportBtn');
    if (exportBtn) {
        exportBtn.addEventListener('click', () => {
            window.graphManager.exportAsImage();
        });
    }

    const fitBtn = document.getElementById('fitBtn');
    if (fitBtn) {
        fitBtn.addEventListener('click', () => {
            window.graphManager.fitToScreen();
        });
    }

    const backBtn = document.getElementById('backBtn');
    if (backBtn) {
        backBtn.addEventListener('click', () => {
            window.history.back();
        });
    }
});
// Scroll animations
class ScrollAnimations {
    constructor() {
        this.elements = document.querySelectorAll('.fade-in');
        this.observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                }
            });
        }, { threshold: 0.1 });
        
        this.init();
    }
    
    init() {
        this.elements.forEach(el => this.observer.observe(el));
    }
}

// Inicializar cuando cargue la página
document.addEventListener('DOMContentLoaded', function() {
    new ScrollAnimations();
});