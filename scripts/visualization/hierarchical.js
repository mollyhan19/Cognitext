Promise.all([
    d3.json('../../data/simp_concept_priorities.json'),
    d3.json('../../data/simp_relation_section_results.json')
]).then(([conceptData, relationData]) => {
    const width = 1200;
    const height = 800;
    const margin = { top: 50, right: 50, bottom: 50, left: 50 };

    const svg = d3.select('#visualization')
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    // Process nodes
    const nodes = Object.entries(conceptData.concepts)
        .map(([id, data]) => ({
            id: id,
            ...data
        }))
        .sort((a, b) => b.total_degree - a.total_degree);

    // Assign levels based on total_degree
    const maxDegree = d3.max(nodes, d => d.total_degree);
    const levels = 5;
    const levelGroups = new Map();

    nodes.forEach(node => {
        const normalizedScore = node.total_degree / maxDegree;
        const level = Math.floor((1 - normalizedScore) * (levels - 1));
        node.level = level;
        
        if (!levelGroups.has(level)) {
            levelGroups.set(level, []);
        }
        levelGroups.get(level).push(node);
    });

    const verticalSpacing = (height - margin.top - margin.bottom) / (levels - 1);
    levelGroups.forEach((nodesInLevel, level) => {
        // Sort nodes within level by total_degree
        nodesInLevel.sort((a, b) => b.total_degree - a.total_degree);
        
        // Calculate horizontal spacing for this level
        const levelWidth = width - margin.left - margin.right;
        const nodeSpacing = levelWidth / (nodesInLevel.length + 1);
        
        // Position nodes
        nodesInLevel.forEach((node, i) => {
            node.x = margin.left + ((i + 1) * nodeSpacing);
            node.y = margin.top + (level * verticalSpacing);
        });
    });

    // Filter and process links
    const validNodeIds = new Set(nodes.map(node => node.id));
    const links = relationData.Tardigrades.relations.filter(relation => 
        validNodeIds.has(relation.source) && validNodeIds.has(relation.target)
    ).map(link => ({
        ...link,
        source: nodes.find(n => n.id === link.source),
        target: nodes.find(n => n.id === link.target)
    }));

    // Draw curved links
    const link = svg.append('g')
        .selectAll('path')
        .data(links)
        .join('path')
        .attr('class', 'link')
        .attr('d', d => {
            const sourceY = d.source.y;
            const targetY = d.target.y;
            const sourceX = d.source.x;
            const targetX = d.target.x;
            const midY = (sourceY + targetY) / 2;
            
            return `M${sourceX},${sourceY}
                    C${sourceX},${midY}
                    ${targetX},${midY}
                    ${targetX},${targetY}`;
        })
        .attr('fill', 'none')
        .attr('stroke', '#A0AEC0')
        .attr('stroke-width', 2)
        .attr('marker-end', 'url(#arrowhead)');

    // Add arrow marker
    svg.append('defs').append('marker')
        .attr('id', 'arrowhead')
        .attr('viewBox', '-0 -5 10 10')
        .attr('refX', 35)
        .attr('refY', 0)
        .attr('orient', 'auto')
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .append('path')
        .attr('d', 'M 0,-5 L 10,0 L 0,5')
        .attr('fill', '#A0AEC0');

    // Draw nodes
    const node = svg.append('g')
        .selectAll('g')
        .data(nodes)
        .join('g')
        .attr('class', 'node')
        .attr('transform', d => `translate(${d.x},${d.y})`);

    // Color scale based on levels
    const colorScale = d3.scaleOrdinal()
        .domain(d3.range(levels))
        .range(['#2B6CB0', '#3182CE', '#4299E1', '#63B3ED', '#90CDF4']);

    // Add circles for nodes
    node.append('circle')
        .attr('r', d => Math.max(30, Math.min(50, d.total_degree * 1.5)))
        .style('fill', d => colorScale(d.level))
        .style('stroke', '#1A365D')
        .style('stroke-width', 2);

    // Add labels with proper text wrapping
    node.append('text')
        .each(function(d) {
            const el = d3.select(this);
            const radius = Math.max(30, Math.min(50, d.total_degree * 1.5));
            const words = d.id.split(/\s+/);
            
            el.style('font-size', '12px')
              .style('fill', 'white')
              .style('text-anchor', 'middle')
              .style('dominant-baseline', 'middle');

            const lineHeight = 14;
            let y = -((words.length - 1) * lineHeight) / 2;

            words.forEach(word => {
                el.append('tspan')
                    .text(word)
                    .attr('x', 0)
                    .attr('y', y);
                y += lineHeight;
            });
        });
    
    node.selectAll('circle')
        .attr('r', d => {
            const baseSize = Math.max(30, Math.min(50, d.total_degree * 1.5));
            return d.level === 0 ? baseSize * 1.5 : baseSize; // Make top level nodes larger
        });

    // Add hover and click interactions for links
    link.on('mouseover', (event, d) => {
            d3.select(event.target)
                .style('stroke', '#4A5568')
                .style('stroke-width', '3px');
        })
        .on('mouseout', (event) => {
            d3.select(event.target)
                .style('stroke', '#A0AEC0')
                .style('stroke-width', '2px');
        })
        .on('click', (event, d) => {
            event.preventDefault();
            event.stopPropagation();
            
            d3.selectAll('.relation-label').remove();
            
            const midX = (d.source.x + d.target.x) / 2;
            const midY = (d.source.y + d.target.y) / 2;
            
            svg.append('g')
                .attr('class', 'relation-label')
                .attr('transform', `translate(${midX},${midY})`)
                .call(g => {
                    const padding = 8;
                    const text = g.append('text')
                        .attr('text-anchor', 'middle')
                        .attr('fill', 'white')
                        .text(d.relation_type);
                    
                    const bbox = text.node().getBBox();
                    
                    g.insert('rect', 'text')
                        .attr('x', bbox.x - padding)
                        .attr('y', bbox.y - padding)
                        .attr('width', bbox.width + (padding * 2))
                        .attr('height', bbox.height + (padding * 2))
                        .attr('fill', '#2D3748')
                        .attr('rx', 4);
                });
        });
}).catch(error => {
    console.error('Error loading the data:', error);
});