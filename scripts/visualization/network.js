Promise.all([
    d3.json('../../data/simp_concept_priorities.json'),
    d3.json('../../data/simp_relation_section_results.json')
]).then(([conceptData, relationData]) => {
    const width = 1200;
    const height = 800;
    const centerX = width / 2;
    const centerY = height / 2;

    const svg = d3.select('#visualization')
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    // Create and sort nodes by total_degree
    const nodes = Object.entries(conceptData.concepts)
        .map(([id, data]) => ({
            id: id,
            ...data
        }))
        .sort((a, b) => b.total_degree - a.total_degree);

    // Calculate tier thresholds
    const nodeCount = nodes.length;
    const topThreshold = Math.floor(nodeCount * 0.33);
    const midThreshold = Math.floor(nodeCount * 0.67);

    // Assign tiers
    nodes.forEach((node, index) => {
        if (index < topThreshold) {
            node.colorTier = 'top';
        } else if (index < midThreshold) {
            node.colorTier = 'mid';
        } else {
            node.colorTier = 'low';
        }
    });

    const maxDegree = d3.max(nodes, d => d.total_degree);
    
    const radiusScale = d3.scaleLinear()
        .domain([0, maxDegree])
        .range([20, 60]);

    const colorScale = d => {
        switch(d.colorTier) {
            case 'top': return '#2B6CB0';
            case 'mid': return '#63B3ED';
            case 'low': return '#CBD5E0';
            default: return '#CBD5E0';
        }
    };

    // Fix highest degree node at center
    nodes[0].fx = centerX;
    nodes[0].fy = centerY;

    // Custom force to keep nodes within bounds
    const boundingForce = () => {
        nodes.forEach(node => {
            const r = radiusScale(node.total_degree);
            if (node !== nodes[0]) { // Don't apply to center node
                node.x = Math.max(r, Math.min(width - r, node.x));
                node.y = Math.max(r, Math.min(height - r, node.y));
            }
        });
    };

    const radialForce = d3.forceRadial(d => {
        if (d.colorTier === 'top') return 150;  // Core concepts stay near the center
        if (d.colorTier === 'mid') return 300;  // Middle concepts are positioned midway
        return 500;  // Detailed concepts move towards the periphery
    }, centerX, centerY).strength(1);  // Strength controls how strictly they follow this pattern

    const simulation = d3.forceSimulation(nodes)
        .force('charge', d3.forceManyBody().strength(-200)) // Repels nodes
        .force('collision', d3.forceCollide().radius(d => radiusScale(d.total_degree) + 5))
        .force('x', d3.forceX(centerX).strength(0.05))  // Helps nodes stay centered
        .force('y', d3.forceY(centerY).strength(0.05))
        .force('radial', radialForce)  // New radial force to organize levels
        .on('tick', () => {
            boundingForce();
            tick();
        });

    // Create node elements
    const node = svg.append('g')
        .selectAll('g')
        .data(nodes)
        .join('g')
        .attr('class', 'node')
        .call(d3.drag()
            .on('start', dragstarted)
            .on('drag', dragged)
            .on('end', dragended));

    node.append('circle')
        .attr('r', d => radiusScale(d.total_degree))
        .style('fill', d => colorScale(d))
        .style('stroke', d => d.colorTier === 'top' ? '#1A365D' : 'none')
        .style('stroke-width', 2);

    node.append('text')
        .each(function(d) {
            const el = d3.select(this);
            const radius = radiusScale(d.total_degree);
            const words = d.id.split(/\s+/);
            
            const maxWidth = radius * 1.6;
            const baseSize = radius / 3;
            const longestWord = words.reduce((a, b) => a.length > b.length ? a : b);
            const fontSize = Math.min(
                baseSize,
                (maxWidth / longestWord.length) * 1.5,
                14
            );
            
            el.style('font-size', `${fontSize}px`)
              .style('font-weight', d.colorTier === 'top' ? 'bold' : 'normal');
    
            const lines = [];
            let currentLine = words[0];
            
            for (let i = 1; i < words.length; i++) {
                const testLine = currentLine + ' ' + words[i];
                const testWidth = testLine.length * fontSize * 0.6; // Approximate width
                
                if (testWidth < maxWidth) {
                    currentLine = testLine;
                } else {
                    lines.push(currentLine);
                    currentLine = words[i];
                }
            }
            lines.push(currentLine);
    
            const lineHeight = fontSize * 1.2;
            const totalHeight = lines.length * lineHeight;
            const startY = -(totalHeight / 2) + (lineHeight / 2);
    
            lines.forEach((line, i) => {
                el.append('tspan')
                    .text(line)
                    .attr('x', 0)
                    .attr('y', startY + (i * lineHeight));
            });
        });


    svg.append('defs').append('marker')
        .attr('id', 'arrowhead')
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 10)  // Adjusted value
        .attr('refY', 0)
        .attr('orient', 'auto')
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .append('path')
        .attr('d', 'M 0,-5 L 10,0 L 0,5')
        .attr('fill', '#A0AEC0');
    

    // Add glow filter
    const defs = svg.append('defs');
    const filter = defs.append('filter')
        .attr('id', 'glow');

    filter.append('feGaussianBlur')
        .attr('stdDeviation', '3')
        .attr('result', 'coloredBlur');

    const feMerge = filter.append('feMerge');
    feMerge.append('feMergeNode')
        .attr('in', 'coloredBlur');
    feMerge.append('feMergeNode')
        .attr('in', 'SourceGraphic');

    // Create links group before nodes for proper layering
    const linksGroup = svg.append('g');  // Links will be drawn first
    const nodesGroup = svg.append('g');  // Nodes will be drawn on top of links

    // Process links data
    const links = relationData.Tardigrades.relations.map(relation => ({
        source: nodes.find(n => n.id === relation.source),
        target: nodes.find(n => n.id === relation.target),
        type: relation.relation_type
    })).filter(link => link.source && link.target);

    // Create tooltip
    const tooltip = d3.select('#visualization')
        .append('div')
        .attr('class', 'tooltip')
        .style('opacity', 0);

    function filterByDepth(depth) {
        const threshold = depth === 'summary' ? topThreshold :
                         depth === 'moderate' ? midThreshold :
                         nodes.length;
        
        // Get visible nodes
        const visibleNodes = nodes.slice(0, threshold);
        const visibleNodeIds = new Set(visibleNodes.map(n => n.id));

        // Filter visible links (connections between visible nodes)
        const visibleLinks = links.filter(link => 
            visibleNodeIds.has(link.source.id) && visibleNodeIds.has(link.target.id)
        );

        // Check for hidden connections
        visibleNodes.forEach(node => {
            // Find all links where this node is source or target
            const nodeLinks = links.filter(link => 
                link.source.id === node.id || link.target.id === node.id
            );
            
            // Check if any of these links connect to hidden nodes
            node.hasHiddenConnections = nodeLinks.some(link => {
                const otherNode = link.source.id === node.id ? link.target : link.source;
                return !visibleNodeIds.has(otherNode.id);
            });
        });

        // Update node visibility and glow effect
        node.style('display', (d, i) => i < threshold ? null : 'none')
            .select('circle')
            .style('filter', d => d.hasHiddenConnections ? 'url(#glow)' : null);

        // Update links
        const link = linksGroup.selectAll('.link')
            .data(visibleLinks, d => `${d.source.id}-${d.target.id}`)
            .join('line')
            .attr('class', 'link')
            .attr('marker-end', 'url(#arrowhead)')
            .style('stroke', '#A0AEC0')
            .style('stroke-width', 2)
            .style('stroke-opacity', 0.3)  // <-- Make links 30% transparent
            .on('mouseover', (event, d) => {
                d3.select(event.target)
                .style('stroke', '#4A5568')
                .style('stroke-width', '3px')
                .style('stroke-opacity', 1);  // Make fully visible on hover
            
            tooltip
                .style('opacity', 1)
                .html(`${d.source.id} <strong>${d.type}</strong> ${d.target.id}`);
            })
            .on('mousemove', (event) => {
                tooltip
                    .style('left', (event.pageX + 10) + 'px')
                    .style('top', (event.pageY - 10) + 'px');
            })
            .on('mouseout', (event) => {
                d3.select(event.target)
                    .style('stroke', '#A0AEC0')
                    .style('stroke-width', '2px')
                    .style('stroke-opacity', 0.5);  // Restore transparency
            })
            .on('click', (event, d) => {
                event.preventDefault();
                event.stopPropagation();
                
                const isTooltipVisible = d3.select(event.target).classed('selected');
                
                d3.selectAll('.permanent-tooltip').remove();
                d3.selectAll('.link').classed('selected', false);
                
                if (!isTooltipVisible) {
                    d3.select(event.target).classed('selected', true);
                    
                    const tooltipX = (d.source.x + d.target.x) / 2;
                    const tooltipY = (d.source.y + d.target.y) / 2;
                    
                    svg.append('g')
                        .attr('class', 'permanent-tooltip')
                        .attr('transform', `translate(${tooltipX},${tooltipY})`)
                        .call(g => {
                            const padding = 8;
                            const text = g.append('text')
                                .attr('text-anchor', 'middle')
                                .attr('fill', 'white')
                                .text(d.type);
                            
                            const bbox = text.node().getBBox();
                            
                            g.insert('rect', 'text')
                                .attr('x', bbox.x - padding)
                                .attr('y', bbox.y - padding)
                                .attr('width', bbox.width + (padding * 2))
                                .attr('height', bbox.height + (padding * 2))
                                .attr('fill', '#2D3748')
                                .attr('rx', 4);
                        });
                }
            });

        // Update simulation
        simulation.nodes(visibleNodes);
        simulation.force('link', d3.forceLink(visibleLinks)
            .id(d => d.id)
            .distance(d => radiusScale(d.source.total_degree) + radiusScale(d.target.total_degree) + 70));
    }

    // Add event listeners for depth buttons
    ['summary', 'moderate', 'detailed'].forEach(depth => {
        document.getElementById(depth).addEventListener('click', () => {
            // Update button states
            document.querySelectorAll('.depth-button').forEach(btn => {
                btn.classList.remove('active');
            });
            document.getElementById(depth).classList.add('active');
            
            // Update visualization
            filterByDepth(depth);
        });
    });

    function tick() {
        linksGroup.selectAll('.link')
            .attr('x1', d => {
                const angle = Math.atan2(d.target.y - d.source.y, d.target.x - d.source.x);
                return d.source.x + Math.cos(angle) * radiusScale(d.source.total_degree);
            })
            .attr('y1', d => {
                const angle = Math.atan2(d.target.y - d.source.y, d.target.x - d.source.x);
                return d.source.y + Math.sin(angle) * radiusScale(d.source.total_degree);
            })
            .attr('x2', d => {
                const angle = Math.atan2(d.source.y - d.target.y, d.source.x - d.target.x);
                return d.target.x + Math.cos(angle) * radiusScale(d.target.total_degree);
            })
            .attr('y2', d => {
                const angle = Math.atan2(d.source.y - d.target.y, d.source.x - d.target.x);
                return d.target.y + Math.sin(angle) * radiusScale(d.target.total_degree);
            });
    
        node.attr('transform', d => `translate(${d.x},${d.y})`);
    }

    function dragstarted(event) {
        if (event.subject === nodes[0]) return; // Prevent dragging center node
        if (!event.active) simulation.alphaTarget(0.3).restart();
        event.subject.fx = event.subject.x;
        event.subject.fy = event.subject.y;
    }

    function dragged(event) {
        if (event.subject === nodes[0]) return; // Prevent dragging center node
        const r = radiusScale(event.subject.total_degree);
        event.subject.fx = Math.max(r, Math.min(width - r, event.x));
        event.subject.fy = Math.max(r, Math.min(height - r, event.y));
    }

    function dragended(event) {
        if (event.subject === nodes[0]) return; // Prevent dragging center node
        if (!event.active) simulation.alphaTarget(0);
        event.subject.fx = null;
        event.subject.fy = null;
    }

    // Initial filter
    filterByDepth('summary');

}).catch(error => {
    console.error('Error loading the data:', error);
});