/**
 * Renderer for concept maps
 * Handles drawing constellations on a canvas
 */
export class ConceptMapRenderer {
    /**
     * Constructor
     * @param {HTMLCanvasElement} canvas - The canvas element to render on
     */
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.colors = [
            '#e1f5fe', '#e8f5e9', '#fff3e0', '#f3e5f5', '#e8eaf6',
            '#ffebee', '#f1f8e9', '#e0f7fa', '#fce4ec', '#e0f2f1'
        ];
        this.strokeColors = [
            '#0288d1', '#2e7d32', '#ef6c00', '#7b1fa2', '#3949ab',
            '#d32f2f', '#689f38', '#0097a7', '#c2185b', '#00796b'
        ];
    }

    /**
     * Render a constellation on the canvas
     * @param {Object} constellation - The constellation definition
     * @param {Array} relations - The relevant concept relations
     */
    renderConstellation(constellation, relations) {
        // Clear the canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Filter relations to include only those in this constellation
        const relevantRelations = relations.filter(rel =>
            constellation.concepts.includes(rel.source.toLowerCase()) &&
            constellation.concepts.includes(rel.target.toLowerCase())
        );

        // Build graph data
        const graphData = this.buildGraphData(relevantRelations);

        // Calculate node positions
        this.calculateNodePositions(graphData, constellation.concepts);

        // Draw the concept map
        this.drawConceptMap(graphData, constellation.name);
    }

    /**
     * Build graph data from relations
     * @param {Array} relations - The concept relations
     * @returns {Object} - Graph data with nodes and edges
     */
    buildGraphData(relations) {
        const graphData = {
            nodes: {},
            edges: []
        };

        // Create unique nodes
        relations.forEach(rel => {
            if (!graphData.nodes[rel.source.toLowerCase()]) {
                graphData.nodes[rel.source.toLowerCase()] = {
                    id: rel.source.toLowerCase(),
                    label: rel.source,
                    color: null,
                    x: null,
                    y: null,
                    radius: null
                };
            }

            if (!graphData.nodes[rel.target.toLowerCase()]) {
                graphData.nodes[rel.target.toLowerCase()] = {
                    id: rel.target.toLowerCase(),
                    label: rel.target,
                    color: null,
                    x: null,
                    y: null,
                    radius: null
                };
            }

            // Add edge
            graphData.edges.push({
                source: rel.source.toLowerCase(),
                sourceLabel: rel.source,
                target: rel.target.toLowerCase(),
                targetLabel: rel.target,
                label: rel.relation_type
            });
        });

        // Assign colors
        let colorIndex = 0;
        for (const nodeId in graphData.nodes) {
            graphData.nodes[nodeId].color = this.colors[colorIndex % this.colors.length];
            graphData.nodes[nodeId].stroke = this.strokeColors[colorIndex % this.strokeColors.length];
            colorIndex++;
        }

        return graphData;
    }

    /**
     * Calculate node positions using a force-directed layout
     * @param {Object} graphData - The graph data with nodes and edges
     * @param {Array} centralConcepts - Key concepts in this constellation
     */
    calculateNodePositions(graphData, centralConcepts) {
        const nodes = Object.values(graphData.nodes);
        const centerX = this.canvas.width / 2;
        const centerY = this.canvas.height / 2;

        // For each node, calculate connections count and determine centrality
        nodes.forEach(node => {
            let connections = 0;
            graphData.edges.forEach(edge => {
                if (edge.source === node.id || edge.target === node.id) {
                    connections++;
                }
            });

            // Size based on connections and centrality
            const isCentral = centralConcepts.indexOf(node.id) < 3; // First 3 concepts are considered central
            node.radius = Math.max(40, Math.min(60, 30 + connections * 3 + (isCentral ? 10 : 0)));
        });

        // Organize nodes in a circle
        const radius = Math.min(this.canvas.width, this.canvas.height) * 0.35;

        // Look for a central concept to place in the middle
        const centralConcept = centralConcepts[0];
        let centralIndex = nodes.findIndex(node => node.id === centralConcept);

        if (centralIndex !== -1) {
            nodes[centralIndex].x = centerX;
            nodes[centralIndex].y = centerY;

            // Remove central node from the array for positioning
            const centralNode = nodes.splice(centralIndex, 1)[0];

            // Position remaining nodes in a circle
            const startAngle = -Math.PI / 2; // Top of the circle
            nodes.forEach((node, i) => {
                const angle = startAngle + ((i + 1) * 2 * Math.PI / (nodes.length + 1));
                node.x = centerX + radius * Math.cos(angle);
                node.y = centerY + radius * Math.sin(angle);
            });

            // Add central node back to the array
            nodes.unshift(centralNode);
        } else {
            // If no central concept, position all nodes evenly
            const startAngle = -Math.PI / 2;
            nodes.forEach((node, i) => {
                const angle = startAngle + (i * 2 * Math.PI / nodes.length);
                node.x = centerX + radius * Math.cos(angle);
                node.y = centerY + radius * Math.sin(angle);
            });
        }

        // Adjust positions to prevent overlaps
        const iterations = 40;
        for (let i = 0; i < iterations; i++) {
            // Apply force-directed algorithm
            this.applyForceDirectedIteration(nodes, graphData.edges);

            // Keep nodes within canvas bounds
            nodes.forEach(node => {
                const padding = node.radius + 10;
                node.x = Math.max(padding, Math.min(this.canvas.width - padding, node.x));
                node.y = Math.max(padding, Math.min(this.canvas.height - padding, node.y));
            });
        }
    }

    /**
     * Apply one iteration of force-directed layout algorithm
     * @param {Array} nodes - The nodes to position
     * @param {Array} edges - The edges connecting nodes
     */
    applyForceDirectedIteration(nodes, edges) {
        // Repulsive forces between nodes
        for (let j = 0; j < nodes.length; j++) {
            for (let k = j + 1; k < nodes.length; k++) {
                const nodeA = nodes[j];
                const nodeB = nodes[k];

                const dx = nodeB.x - nodeA.x;
                const dy = nodeB.y - nodeA.y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                const minDistance = nodeA.radius + nodeB.radius + 20;

                if (distance < minDistance) {
                    const repulsionForce = 3;
                    const fx = (dx / distance) * repulsionForce * (minDistance - distance) / minDistance;
                    const fy = (dy / distance) * repulsionForce * (minDistance - distance) / minDistance;

                    nodeA.x -= fx;
                    nodeA.y -= fy;
                    nodeB.x += fx;
                    nodeB.y += fy;
                }
            }
        }

        // Attractive forces for connected nodes
        edges.forEach(edge => {
            const sourceNode = nodes.find(n => n.id === edge.source);
            const targetNode = nodes.find(n => n.id === edge.target);

            if (sourceNode && targetNode) {
                const dx = targetNode.x - sourceNode.x;
                const dy = targetNode.y - sourceNode.y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance > 300) {
                    const attractionForce = 0.01;
                    const fx = dx * attractionForce;
                    const fy = dy * attractionForce;

                    sourceNode.x += fx;
                    sourceNode.y += fy;
                    targetNode.x -= fx;
                    targetNode.y -= fy;
                }
            }
        });
    }

    /**
     * Draw the concept map on the canvas
     * @param {Object} graphData - The graph data with nodes and edges
     */
    drawConceptMap(graphData) {
        // Draw edges first
        graphData.edges.forEach(edge => {
            this.drawEdge(edge, graphData.nodes, graphData.edges);
        });

        // Draw nodes
        for (const nodeId in graphData.nodes) {
            this.drawNode(graphData.nodes[nodeId]);
        }
    }

    /**
     * Draw a node on the canvas
     * @param {Object} node - The node to draw
     */
    drawNode(node) {
        // Draw node background
        this.ctx.beginPath();
        this.ctx.arc(node.x, node.y, node.radius, 0, 2 * Math.PI);
        this.ctx.fillStyle = node.color;
        this.ctx.fill();
        this.ctx.lineWidth = 2;
        this.ctx.strokeStyle = node.stroke;
        this.ctx.stroke();

        // Draw node label
        this.ctx.font = 'bold 14px Arial';
        this.ctx.fillStyle = '#333';
        this.ctx.textAlign = 'center';

        // Handle multi-line labels
        const words = node.label.split(' ');
        let line = '';
        let lines = [];
        const maxWidth = node.radius * 1.5;

        for (let i = 0; i < words.length; i++) {
            const testLine = line + words[i] + ' ';
            const metrics = this.ctx.measureText(testLine);

            if (metrics.width > maxWidth && i > 0) {
                lines.push(line);
                line = words[i] + ' ';
            } else {
                line = testLine;
            }
        }
        lines.push(line);

        // Center text vertically
        const lineHeight = 16;
        let y = node.y - ((lines.length - 1) * lineHeight / 2);

        lines.forEach(line => {
            this.ctx.fillText(line, node.x, y);
            y += lineHeight;
        });
    }

    /**
     * Draw an edge between two nodes, handling bidirectional relationships
     * @param {Object} edge - The edge to draw
     * @param {Object} nodes - The nodes map
     * @param {Array} allEdges - All edges in the graph for detecting bidirectional relationships
     */
    drawEdge(edge, nodes, allEdges) {
        const sourceNode = nodes[edge.source];
        const targetNode = nodes[edge.target];

        if (!sourceNode || !targetNode) return;

        // Check if there's a reverse edge (bidirectional relationship)
        const reverseEdge = allEdges.find(e =>
            e.source === edge.target &&
            e.target === edge.source
        );

        // Calculate edge endpoints
        const dx = targetNode.x - sourceNode.x;
        const dy = targetNode.y - sourceNode.y;
        const angle = Math.atan2(dy, dx);

        // For parallel edges in bidirectional relationships, offset the path
        const offset = reverseEdge ? 8 : 0; // Offset in pixels

        // Calculate offset coordinates
        let startX, startY, endX, endY;

        if (reverseEdge) {
            // If this is a bidirectional relationship, offset this edge to one side
            const offsetX = offset * Math.cos(angle + Math.PI/2);
            const offsetY = offset * Math.sin(angle + Math.PI/2);

            startX = sourceNode.x + sourceNode.radius * Math.cos(angle) + offsetX;
            startY = sourceNode.y + sourceNode.radius * Math.sin(angle) + offsetY;
            endX = targetNode.x - targetNode.radius * Math.cos(angle) + offsetX;
            endY = targetNode.y - targetNode.radius * Math.sin(angle) + offsetY;
        } else {
            // Standard edge
            startX = sourceNode.x + sourceNode.radius * Math.cos(angle);
            startY = sourceNode.y + sourceNode.radius * Math.sin(angle);
            endX = targetNode.x - targetNode.radius * Math.cos(angle);
            endY = targetNode.y - targetNode.radius * Math.sin(angle);
        }

        // Draw the edge line
        this.ctx.beginPath();
        this.ctx.moveTo(startX, startY);
        this.ctx.lineTo(endX, endY);
        this.ctx.strokeStyle = '#666';
        this.ctx.lineWidth = 1.5;
        this.ctx.stroke();

        // Draw arrow
        const arrowSize = 8;
        this.ctx.beginPath();
        this.ctx.moveTo(endX, endY);
        this.ctx.lineTo(
            endX - arrowSize * Math.cos(angle - Math.PI/6),
            endY - arrowSize * Math.sin(angle - Math.PI/6)
        );
        this.ctx.lineTo(
            endX - arrowSize * Math.cos(angle + Math.PI/6),
            endY - arrowSize * Math.sin(angle + Math.PI/6)
        );
        this.ctx.closePath();
        this.ctx.fillStyle = '#666';
        this.ctx.fill();

        // Draw the edge label with better positioning
        const midX = (startX + endX) / 2;
        const midY = (startY + endY) / 2;

        // Position label slightly off the line with bigger offset for parallel edges
        const labelOffset = reverseEdge ? 20 : 10;
        const labelX = midX + (labelOffset * Math.cos(angle + Math.PI/2));
        const labelY = midY + (labelOffset * Math.sin(angle + Math.PI/2));

        this.ctx.font = '12px Arial';

        // Add a white background for better readability
        const label = edge.label;
        const labelWidth = this.ctx.measureText(label).width + 10;
        this.ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
        this.ctx.fillRect(labelX - labelWidth/2, labelY - 8, labelWidth, 16);

        this.ctx.fillStyle = '#333';
        this.ctx.textAlign = 'center';
        this.ctx.fillText(label, labelX, labelY);
    }
}