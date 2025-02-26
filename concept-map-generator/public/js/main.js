// Import modules
import { LLMProcessor } from './llmProcessor.js';
import { ConceptMapRenderer } from './conceptRenderer.js';

// DOM elements
const jsonInput = document.getElementById('jsonInput');
const generateButton = document.getElementById('generateButton');
const loadFileButton = document.getElementById('loadFileButton');
const fileInput = document.getElementById('fileInput');
const sampleDataButton = document.getElementById('sampleDataButton');
const statusP = document.getElementById('status');
const loadingIndicator = document.getElementById('loadingIndicator');
const constellationContainer = document.getElementById('constellation-container');
const constellationTitle = document.getElementById('constellation-title');
const constellationDescription = document.getElementById('constellation-description');
const prevButton = document.getElementById('prevButton');
const nextButton = document.getElementById('nextButton');
const pageIndicator = document.getElementById('pageIndicator');
const canvas = document.getElementById('conceptMapCanvas');

// Initialize the processor and renderer
const llmProcessor = new LLMProcessor();
const renderer = new ConceptMapRenderer(canvas);

// Constellation data
let constellations = [];
let allRelations = [];
let currentConstellationIndex = 0;

// Event listeners
generateButton.addEventListener('click', generateConstellations);
loadFileButton.addEventListener('click', function() {
    fileInput.click();
});
fileInput.addEventListener('change', loadJsonFromFile);
sampleDataButton.addEventListener('click', loadSampleData);
prevButton.addEventListener('click', showPreviousConstellation);
nextButton.addEventListener('click', showNextConstellation);

// Function to load JSON from a file upload
function loadJsonFromFile(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();

    reader.onload = function(e) {
        try {
            const content = e.target.result;
            const data = JSON.parse(content);

            // Display in the textarea
            jsonInput.value = JSON.stringify(data, null, 2);
            statusP.textContent = `File "${file.name}" loaded successfully. Click 'Generate Constellation Maps' to process.`;
        } catch (error) {
            console.error('Error parsing JSON file:', error);
            statusP.textContent = 'Error: Invalid JSON file format.';
        }
    };

    reader.onerror = function() {
        statusP.textContent = 'Error reading file.';
    };

    reader.readAsText(file);
}

// Load sample tardigrade data
function loadSampleData() {
    fetch('/sample-data.json')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            jsonInput.value = JSON.stringify(data, null, 2);
            statusP.textContent = "Sample data loaded. Click 'Generate Constellation Maps' to process.";
        })
        .catch(error => {
            console.error('Error loading sample data:', error);
            statusP.textContent = "Error loading sample data. Please upload your own JSON file instead.";

            // Fallback to a minimal sample if file loading fails
            const fallbackData = {
                "Tardigrades": {
                    "category": "biology",
                    "relations": [
                        {
                            "source": "tardigrades",
                            "relation_type": "capable of",
                            "target": "cryptobiosis"
                        },
                        {
                            "source": "cryptobiosis",
                            "relation_type": "results in",
                            "target": "desiccated cyst (tun state)"
                        },
                        {
                            "source": "desiccated cyst (tun state)",
                            "relation_type": "provides",
                            "target": "impact resistance"
                        }
                    ]
                }
            };

            jsonInput.value = JSON.stringify(fallbackData, null, 2);
        });
}

// Generate constellations from the data
async function generateConstellations() {
    try {
        // Check if JSON input is provided
        if (!jsonInput.value.trim()) {
            statusP.textContent = "Please enter or load concept relation data first.";
            return;
        }

        // Show loading indicator
        loadingIndicator.style.display = 'flex';
        statusP.textContent = "Processing with LLM. This may take a minute...";
        generateButton.disabled = true;

        // Parse JSON input
        const jsonData = JSON.parse(jsonInput.value);

        // Process with LLM
        const result = await llmProcessor.processConceptData(jsonData);

        // Store constellations and relations
        constellations = result.constellations;

        // Get all relations from the input data
        const domainName = Object.keys(jsonData)[0];
        allRelations = jsonData[domainName].relations;

        // Hide loading indicator
        loadingIndicator.style.display = 'none';
        generateButton.disabled = false;

        if (constellations.length === 0) {
            statusP.textContent = "No valid constellations could be generated from the data.";
            return;
        }

        // Show the constellation container
        constellationContainer.style.display = 'block';

        // Set up navigation
        currentConstellationIndex = 0;
        updateNavigationButtons();

        // Show the first constellation
        showConstellation(currentConstellationIndex);

        statusP.textContent = `Generated ${constellations.length} concept map constellations.`;
    } catch (error) {
        console.error('Error generating constellations:', error);
        loadingIndicator.style.display = 'none';
        generateButton.disabled = false;
        statusP.textContent = `Error: ${error.message}`;
    }
}

// Show the constellation at the specified index
function showConstellation(index) {
    const constellation = constellations[index];

    // Set title and description
    constellationTitle.textContent = constellation.name;
    constellationDescription.textContent = constellation.description;

    // Update page indicator
    pageIndicator.textContent = `Constellation ${index + 1} of ${constellations.length}`;

    // Render the constellation
    renderer.renderConstellation(constellation, allRelations);
}

// Show the previous constellation
function showPreviousConstellation() {
    if (currentConstellationIndex > 0) {
        currentConstellationIndex--;
        showConstellation(currentConstellationIndex);
        updateNavigationButtons();
    }
}

// Show the next constellation
function showNextConstellation() {
    if (currentConstellationIndex < constellations.length - 1) {
        currentConstellationIndex++;
        showConstellation(currentConstellationIndex);
        updateNavigationButtons();
    }
}

// Update navigation button states
function updateNavigationButtons() {
    prevButton.disabled = currentConstellationIndex === 0;
    nextButton.disabled = currentConstellationIndex === constellations.length - 1;
}