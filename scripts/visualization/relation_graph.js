class RelationGraph {
    constructor() {
        console.log("Initializing RelationGraph...");
        this.svg = null;
        this.width = 800;
        this.height = 600;
        this.simulation = null;
        this.activeArticle = '';
        this.graphData = { nodes: [], links: [] };
        this.baseNodeRadius = 20;
        this.maxNodeRadius = 50;
        
        this.init();
    }

    async init() {
        try {
            console.log("Starting data loading...");
            
            const relationsResponse = await fetch('../data/relations/master_relations_section.json');
            console.log("Relations response:", relationsResponse.ok);
            const conceptsResponse = await fetch('../data/entities/cleaned_entity_section_results.json');
            console.log("Concepts response:", conceptsResponse.ok);

            if (!relationsResponse.ok || !conceptsResponse.ok) {
                throw new Error('Failed to load data files');
            }

            const relationsData = await relationsResponse.json();
            const conceptsData = await conceptsResponse.json();

            console.log("Data loaded successfully");
            console.log("Available articles:", Object.keys(relationsData.articles));

            // Setup article selector
            const articleSelect = document.getElementById('articleSelect');
            if (!articleSelect) {
                throw new Error('Article select element not found');
            }

            const articles = Object.keys(relationsData.articles);
            
            articles.forEach(article => {
                const option = document.createElement('option');
                option.value = option.textContent = article;
                articleSelect.appendChild(option);
            });

            this.activeArticle = articles[0];
            articleSelect.value = this.activeArticle;

            // Setup event listener for article selection
            articleSelect.addEventListener('change', (e) => {
                this.activeArticle = e.target.value;
                this.processData(relationsData, conceptsData);
            });

            // Initial data processing
            this.processData(relationsData, conceptsData);

        } catch (error) {
            console.error('Error in initialization:', error);
            document.getElementById('graph').innerHTML = `
                <p style="color: red; padding: 20px;">
                    Error loading data: ${error.message}<br>
                    <small>Check console for more details</small>
                </p>`;
        }
    }

    processData(relationsData, conceptsData) {
        const relations = relationsData.articles[this.activeArticle].relations;
        const concepts = conceptsData[this.activeArticle]?.entities || [];

        // Create frequency map
        const frequencyMap = new Map();
        concepts.forEach(concept => {
            frequencyMap.set(concept.id.toLowerCase(), concept.frequency);
        });

        // Create nodes
        const nodesSet = new Set();
        relations.forEach(relation => {
            nodesSet.add(relation.source.toLowerCase());
            nodesSet.add(relation.target.toLowerCase());
        });

        const nodes = Array.from(nodesSet).map(id => ({
            id: id,
            frequency: frequencyMap.get(id) || 1
        }));

        // Create links
        const links = relations.map(relation => ({
            source: relation.source.toLowerCase(),
            target: relation.target.toLowerCase(),
            type: relation.relation_type,
            evidence: relation.evidence
        }));

        this.graphData = { nodes, links };
        this.createVisualization();
    }

    createVisualization() {
        // Clear previous visualization
        d3.select('#graph').selectAll('*').remove();

        // Create SVG
        this.svg = d3.select('#graph')
            .append('svg')
            .attr('width', this.width)
            .attr('height', this.height);

        // Create frequency scale
        const frequencyExtent = d3.extent(this.graphData.nodes, d => d.frequency);
        const radiusScale = d3.scaleLinear()
            .domain(frequencyExtent)
            .range([this.baseNodeRadius, this.maxNodeRadius]);

        // Create arrow marker
        this.svg.append('defs').append('marker')
            .attr('id', 'arrowhead')
            .attr('viewBox', '-10 -10 20 20')
            .attr('refX', 25)
            .attr('refY', 0)
            .attr('markerWidth', 6)
            .attr('markerHeight', 6)
            .attr('orient', 'auto')
            .append('path')
            .attr('d', 'M-10,-10 L0,0 L-10,10')
            .attr('fill', '#999');

        // Create links
        const links = this.svg.append('g')
            .selectAll('line')
            .data(this.graphData.links)
            .enter()
            .append('line')
            .attr('stroke', '#999')
            .attr('stroke-width', 1.5)
            .attr('marker-end', 'url(#arrowhead)')
            .on('click', (event, d) => {
                const evidenceBox = document.getElementById('evidence');
                evidenceBox.textContent = d.evidence;
                evidenceBox.style.display = 'block';
            });

        // Create link labels
        const linkLabels = this.svg.append('g')
            .selectAll('text')
            .data(this.graphData.links)
            .enter()
            .append('text')
            .attr('class', 'link-label')
            .style('font-size', '8px')
            .text(d => d.type);

        // Create nodes
        const nodes = this.svg.append('g')
            .selectAll('g')
            .data(this.graphData.nodes)
            .enter()
            .append('g');

        function wrap(text, width) {
            text.each(function() {
                const text = d3.select(this);
                const words = text.text().split(/\s+/);
                let line = [];
                let lineNumber = 0;
                const lineHeight = 1.1;
                const y = text.attr('y');
                const dy = parseFloat(text.attr('dy'));
                text.text(null);
                
                let tspan = text.append('tspan')
                    .attr('x', 0)
                    .attr('y', y)
                    .attr('dy', dy + 'em');
        
                words.forEach(word => {
                    line.push(word);
                    tspan.text(line.join(' '));
                    if (tspan.node().getComputedTextLength() > width) {
                        line.pop();
                        tspan.text(line.join(' '));
                        line = [word];
                        tspan = text.append('tspan')
                            .attr('x', 0)
                            .attr('dy', lineHeight + 'em')
                            .text(word);
                        lineNumber++;
                    }
                });
            });
        }

        nodes.append('circle')
            .attr('r', d => radiusScale(d.frequency))
            .attr('fill', '#69b3a2')
            .attr('stroke', '#fff')
            .attr('stroke-width', 2);

        nodes.append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', '0em')
        .style('fill', 'white')
        .style('font-size', '8px')
        .text(d => d.id)
        .call(wrap, d => radiusScale(d.frequency));

        nodes.append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', '1.5em')  // Position it below the main text
        .style('fill', 'white')
        .style('font-size', '6px')  // Directly set smaller font size
        .text(d => `(${d.frequency || 1})`);

        // Create simulation
        this.simulation = d3.forceSimulation(this.graphData.nodes)
            .force('link', d3.forceLink(this.graphData.links).id(d => d.id).distance(150))
            .force('charge', d3.forceManyBody().strength(-300))
            .force('center', d3.forceCenter(this.width / 2, this.height / 2))
            .force('collision', d3.forceCollide().radius(d => radiusScale(d.frequency) * 1.2));

        // Add tick behavior
        this.simulation.on('tick', () => {
            links
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);

            linkLabels
                .attr('x', d => (d.source.x + d.target.x) / 2)
                .attr('y', d => (d.source.y + d.target.y) / 2);

            nodes.attr('transform', d => `translate(${d.x},${d.y})`);
        });

        // Add drag behavior
        nodes.call(d3.drag()
            .on('start', (event, d) => {
                if (!event.active) this.simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            })
            .on('drag', (event, d) => {
                d.fx = event.x;
                d.fy = event.y;
            })
            .on('end', (event, d) => {
                if (!event.active) this.simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            }));
    }
}

document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM loaded, creating RelationGraph...");
    new RelationGraph();
});