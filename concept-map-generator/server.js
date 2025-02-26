// ES Module syntax
import express from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';
import fetch from 'node-fetch';

// Load environment variables from .env file
dotenv.config();

// Set up __dirname equivalent for ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Create Express app
const app = express();
const PORT = process.env.PORT || 3000;

// Enable middleware
app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use(express.static(path.join(__dirname, 'public')));

// Endpoint to proxy OpenAI API requests
app.post('/api/generate-constellations', async (req, res) => {
  try {
    const apiKey = process.env.OPENAI_API_KEY;

    if (!apiKey) {
      return res.status(500).json({
        error: 'API key not configured on server. Please add it to your .env file.'
      });
    }

    const { prompt } = req.body;

    console.log('Processing request with LLM...');

    // Make request to OpenAI
    const response = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        model: 'gpt-4o', // Can be changed to gpt-3.5-turbo
        messages: [
          {
            role: 'system',
            content: 'You are a helpful assistant specialized in analyzing concept maps and knowledge graphs.'
          },
          {
            role: 'user',
            content: prompt
          }
        ],
        temperature: 0.7,
        max_tokens: 1500
      })
    });

    if (!response.ok) {
      const errorData = await response.json();
      console.error('OpenAI API error:', errorData);
      return res.status(response.status).json({
        error: `OpenAI API error: ${errorData.error?.message || 'Unknown error'}`
      });
    }

    const data = await response.json();
    console.log('LLM processing complete');

    res.json(data);
  } catch (error) {
    console.error('Server error:', error);
    res.status(500).json({ error: `Server error: ${error.message}` });
  }
});

// Endpoint to handle file parsing directly on the server
app.post('/api/parse-json', express.text({ limit: '10mb' }), (req, res) => {
  try {
    // Parse the JSON content
    const parsedData = JSON.parse(req.body);
    res.json(parsedData);
  } catch (error) {
    res.status(400).json({ error: `Invalid JSON: ${error.message}` });
  }
});

// Serve the main HTML file for all other routes
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Start the server
app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
  console.log(`Make sure you've added your OpenAI API key to the .env file!`);
});