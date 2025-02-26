/**
 * LLM Processor for concept map analysis
 * This class handles interaction with the backend API
 */
export class LLMProcessor {
    constructor() {
        this.isProcessing = false;
    }

    /**
     * Process concept data to generate constellation definitions
     * @param {Object} jsonData - The concept relation data
     * @returns {Promise<Object>} - The processed constellation definitions
     */
    async processConceptData(jsonData) {
        if (this.isProcessing) {
            throw new Error('Already processing a request. Please wait.');
        }

        this.isProcessing = true;

        try {
            // Extract the domain name and relations
            const domainName = Object.keys(jsonData)[0];
            const domain = jsonData[domainName];
            const relations = domain.relations;

            // Generate constellation definitions
            const constellations = await this.generateConstellationDefinitions(domainName, domain.category, relations);

            return {
                domainName,
                category: domain.category,
                constellations
            };
        } catch (error) {
            console.error('Error processing concept data:', error);
            throw error;
        } finally {
            this.isProcessing = false;
        }
    }

    /**
     * Generate constellation definitions using the LLM
     * @param {string} domainName - The name of the concept domain
     * @param {string} category - The category of the domain
     * @param {Array} relations - The concept relations
     * @returns {Promise<Array>} - Array of constellation definitions
     */
    async generateConstellationDefinitions(domainName, category, relations) {
        // Step 1: Identify common concepts by frequency
        const conceptFrequency = this.analyzeConceptFrequency(relations);
        const topConcepts = Object.entries(conceptFrequency)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 15)
            .map(([concept]) => concept);

        // Step 2: Find potential themes by analyzing relation types
        const relationTypes = new Set(relations.map(rel => rel.relation_type));

        // Step 3: Prepare the prompt for the LLM
        const prompt = this.createConstellationPrompt(domainName, category, relations, topConcepts, Array.from(relationTypes));

        // Step 4: Send the request to the server
        const response = await this.callLLM(prompt);

        // Step 5: Parse the LLM response
        return this.parseConstellationResponse(response, relations);
    }

    /**
     * Analyze the frequency of concepts in the relations
     * @param {Array} relations - The concept relations
     * @returns {Object} - Concept frequency map
     */
    analyzeConceptFrequency(relations) {
        const conceptCount = {};

        relations.forEach(rel => {
            conceptCount[rel.source] = (conceptCount[rel.source] || 0) + 1;
            conceptCount[rel.target] = (conceptCount[rel.target] || 0) + 1;
        });

        return conceptCount;
    }

    /**
     * Create a prompt for the LLM to generate constellation definitions
     * @param {string} domainName - The name of the concept domain
     * @param {string} category - The category of the domain
     * @param {Array} relations - The concept relations
     * @param {Array} topConcepts - The most frequently occurring concepts
     * @param {Array} relationTypes - The types of relations in the data
     * @returns {string} - The prepared prompt
     */
    createConstellationPrompt(domainName, category, relations, topConcepts, relationTypes) {
        // Sample a subset of relations to avoid token limits
        const sampleRelations = relations.length > 50
            ? this.sampleRelations(relations, 50)
            : relations;

        return `
You are an expert in knowledge visualization and concept mapping. I have a dataset of concept relations about "${domainName}" in the category of "${category}".

I need you to identify 3-5 meaningful "concept constellations" from this data. A constellation is a group of closely related concepts that form a coherent theme or cycle.

Here are some of the most frequently occurring concepts:
${topConcepts.join(', ')}

Here are the types of relationships in the data:
${relationTypes.join(', ')}

Here's a sample of the concept relations:
${JSON.stringify(sampleRelations, null, 2)}

For each constellation:
1. Provide a clear name (e.g., "${domainName} Process Cycle")
2. Write a brief description explaining the theme
3. List 4-8 key concepts that should be included in this constellation

Return your response in this JSON format:
{
  "constellations": [
    {
      "name": "Name of constellation 1",
      "description": "Brief description of what this constellation represents",
      "concepts": ["concept1", "concept2", "concept3", "concept4"]
    },
    // Additional constellations...
  ]
}

Focus on creating meaningful groupings that illustrate important relationships, cycles, or themes in the domain.
`;
    }

    /**
     * Sample a subset of relations to stay within token limits
     * @param {Array} relations - The concept relations
     * @param {number} count - The number of relations to sample
     * @returns {Array} - Sampled relations
     */
    sampleRelations(relations, count) {
        // Shuffle and take the first 'count' items
        return [...relations]
            .sort(() => 0.5 - Math.random())
            .slice(0, count);
    }

    /**
     * Call the server API with the prepared prompt
     * @param {string} prompt - The prompt for the LLM
     * @returns {Promise<string>} - The LLM response
     */
    async callLLM(prompt) {
        try {
            // Call the server endpoint instead of OpenAI directly
            const response = await fetch('/api/generate-constellations', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ prompt })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(`API error: ${errorData.error || 'Unknown error'}`);
            }

            const data = await response.json();
            return data.choices[0].message.content;
        } catch (error) {
            console.error('Error calling API:', error);
            throw new Error(`Failed to call API: ${error.message}`);
        }
    }

    /**
     * Parse the LLM response to extract constellation definitions
     * @param {string} response - The raw LLM response
     * @param {Array} allRelations - All concept relations (to validate the response)
     * @returns {Array} - Processed constellation definitions
     */
    parseConstellationResponse(response, allRelations) {
        try {
            // Extract JSON from the response (in case there's explanatory text)
            const jsonMatch = response.match(/\{[\s\S]*\}/);
            if (!jsonMatch) {
                throw new Error('Could not find JSON in LLM response');
            }

            const parsedResponse = JSON.parse(jsonMatch[0]);
            const constellations = parsedResponse.constellations;

            if (!constellations || !Array.isArray(constellations)) {
                throw new Error('Invalid constellation format in LLM response');
            }

            // Validate and normalize the constellations
            return constellations.map(constellation => {
                // Normalize concept names to lowercase for matching
                const normalizedConcepts = (constellation.concepts || [])
                    .map(concept => concept.toLowerCase());

                // Return the validated constellation
                return {
                    name: constellation.name || 'Unnamed Constellation',
                    description: constellation.description || 'No description provided',
                    concepts: normalizedConcepts
                };
            });
        } catch (error) {
            console.error('Error parsing LLM response:', error, response);

            // Fallback to basic constellations if parsing fails
            return this.generateFallbackConstellations(allRelations);
        }
    }

    /**
     * Generate basic fallback constellations if LLM parsing fails
     * @param {Array} relations - All concept relations
     * @returns {Array} - Basic constellation definitions
     */
    generateFallbackConstellations(relations) {
        const conceptFrequency = this.analyzeConceptFrequency(relations);
        const topConcepts = Object.entries(conceptFrequency)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 12)
            .map(([concept]) => concept);

        // Split into two constellations
        const firstHalf = topConcepts.slice(0, 6);
        const secondHalf = topConcepts.slice(6);

        return [
            {
                name: 'Primary Concept Cluster',
                description: 'A constellation of the most connected concepts in the knowledge domain.',
                concepts: firstHalf.map(c => c.toLowerCase())
            },
            {
                name: 'Secondary Concept Cluster',
                description: 'Additional important concepts and their relationships.',
                concepts: secondHalf.map(c => c.toLowerCase())
            }
        ];
    }
}