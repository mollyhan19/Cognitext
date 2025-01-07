import networkx as nx
import json
from pathlib import Path
import matplotlib.pyplot as plt
from typing import Dict, List

class ConceptGraph:
    def __init__(self):
        self.G = nx.Graph()  # Create undirected graph

    def load_from_json(self, json_path: str):
        """Load concepts from the analysis results JSON file."""
        with open(json_path, 'r') as f:
            data = json.load(f)

        # Get the first article's results (assuming one article for now)
        article_data = next(iter(data["analysis_results"].values()))

        # Add nodes (concepts)
        for entity in article_data["entities"]:
            self.G.add_node(
                entity["id"],
                frequency=entity["frequency"],
                variants=entity["variants"],
                appearances=entity["appearances"]
            )

        # Initialize basic edges based on paragraph co-occurrence
        self._create_paragraph_based_edges()

    def _create_paragraph_based_edges(self):
        """Create edges between concepts that appear in the same paragraph."""
        # Create dictionary of concepts by paragraph
        para_concepts = {}
        for node, attrs in self.G.nodes(data=True):
            for appearance in attrs['appearances']:
                para_num = appearance['paragraph']
                if para_num not in para_concepts:
                    para_concepts[para_num] = []
                para_concepts[para_num].append(node)

        # Create edges between concepts in same paragraph
        for para_num, concepts in para_concepts.items():
            for i in range(len(concepts)):
                for j in range(i + 1, len(concepts)):
                    # Add edge if it doesn't exist or increment weight if it does
                    if self.G.has_edge(concepts[i], concepts[j]):
                        self.G[concepts[i]][concepts[j]]['weight'] += 1
                    else:
                        self.G.add_edge(concepts[i], concepts[j], weight=1)

    def get_central_concepts(self, top_n: int = 10) -> List[Dict]:
        """Get top N central concepts based on degree centrality."""
        centrality = nx.degree_centrality(self.G)
        sorted_concepts = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
        return sorted_concepts[:top_n]

    def get_related_concepts(self, concept_id: str) -> List[Dict]:
        """Get concepts related to a given concept based on edge weight."""
        if concept_id not in self.G:
            return []

        related = []
        for neighbor in self.G.neighbors(concept_id):
            related.append({
                'concept': neighbor,
                'weight': self.G[concept_id][neighbor]['weight'],
                'frequency': self.G.nodes[neighbor]['frequency']
            })

        return sorted(related, key=lambda x: x['weight'], reverse=True)

    def visualize(self,
                  min_frequency: int = 3,
                  min_edge_weight: int = 2,
                  node_size_factor: float = 100,
                  with_labels: bool = True):
        """
        Visualize the concept graph with improved readability and legend.
        """
        H = self.G.copy()

        # Filter nodes and edges as before...

        plt.figure(figsize=(20, 20))
        pos = nx.kamada_kawai_layout(H)

        # Draw nodes with consistent style
        node_sizes = [H.nodes[node]['frequency'] * node_size_factor for node in H.nodes()]

        # Draw all nodes with consistent style - outlined circles
        nx.draw_networkx_nodes(H, pos,
                               node_size=node_sizes,
                               node_color='white',
                               edgecolors='lightblue',
                               linewidths=2)

        # Draw edges
        nx.draw_networkx_edges(H, pos,
                               width=1,
                               alpha=0.4,
                               edge_color='gray')

        if with_labels:
            # Increase font size and add padding
            label_pos = {k: (v[0], v[1] + 0.1) for k, v in pos.items()}
            nx.draw_networkx_labels(H, label_pos,
                                    font_size=12,  # Increased font size
                                    font_weight='bold')

        # Add legend
        frequencies = [H.nodes[node]['frequency'] for node in H.nodes()]
        plt.legend(['Node size indicates frequency (range: {}-{})'.format(
            min(frequencies), max(frequencies))],
            loc='upper left',
            fontsize=14,
            bbox_to_anchor=(0, 1.1))

        plt.title("Key Concept Relationships", fontsize=16, pad=20)
        plt.axis('off')
        plt.tight_layout()
        plt.show()

    def visualize_top_concepts(self, top_n: int = 15, node_size_factor: float = 100):
        """
        Visualize the top N most frequent concepts with proportional node sizes and the relationships between them.
        """
        # Get top N concepts by frequency
        top_concepts = sorted(
            self.G.nodes(data=True),
            key=lambda x: x[1]['frequency'],
            reverse=True
        )[:top_n]

        # Create a subgraph with only top concepts
        H = self.G.subgraph([concept[0] for concept in top_concepts])

        plt.figure(figsize=(20, 20))
        pos = nx.spring_layout(H, k=2, iterations=50)  # Increased k for more spacing

        # Calculate node sizes proportional to frequency
        max_freq = max(dict(H.nodes(data=True)).items(), key=lambda x: x[1]['frequency'])[1]['frequency']
        node_sizes = [
            (H.nodes[node]['frequency'] / max_freq) * node_size_factor * 1000  # Scale factor increased
            for node in H.nodes()
        ]

        # Draw nodes
        nx.draw_networkx_nodes(H, pos,
                               node_size=node_sizes,
                               node_color='white',
                               edgecolors='lightblue',
                               linewidths=2)

        # Draw edges
        edge_width = [H[u][v]['weight'] for u, v in H.edges()]
        nx.draw_networkx_edges(H, pos,
                               width=edge_width,
                               alpha=0.6,
                               edge_color='gray')

        # Add labels with frequency
        labels = {
            node: f"{node}\n(freq: {H.nodes[node]['frequency']})"
            for node in H.nodes()
        }

        # Adjust label positions based on node sizes
        label_pos = {k: (v[0], v[1] + 0.02) for k, v in pos.items()}
        nx.draw_networkx_labels(H, label_pos,
                                labels=labels,
                                font_size=12,
                                font_weight='bold')

        plt.title(f"Top {top_n} Most Frequent Concepts", fontsize=16, pad=20)
        plt.axis('off')
        plt.tight_layout()
        plt.show()

        # Print the top concepts and their frequencies
        print(f"\nTop {top_n} concepts by frequency:")
        for concept, data in top_concepts:
            print(f"{concept}: {data['frequency']} occurrences")

    def print_graph_stats(self):
        """Print basic statistics about the graph."""
        print(f"Number of concepts (nodes): {self.G.number_of_nodes()}")
        print(f"Number of relationships (edges): {self.G.number_of_edges()}")
        print("\nTop 10 most frequent concepts:")
        sorted_nodes = sorted(
            self.G.nodes(data=True),
            key=lambda x: x[1]['frequency'],
            reverse=True
        )
        for node, data in sorted_nodes[:10]:
            print(f"- {node}: {data['frequency']} occurrences")

    def save_graph(self, path: str, format: str = "graphml"):
        """
        Save the graph in various formats.
        Supported formats:
        - gexf (Good for Gephi visualization)
        - graphml (Standard graph format)
        - gml (Graph Modeling Language)
        - pajek (Simple network format)
        - pickle (Python serialization)
        """
        path = Path(path)
        if not path.parent.exists():
            path.parent.mkdir(parents=True)

        if format == "graphml":
            nx.write_graphml(self.G, path.with_suffix(".graphml"))
        elif format == "gml":
            nx.write_gml(self.G, path.with_suffix(".gml"))
        elif format == "pajek":
            nx.write_pajek(self.G, path.with_suffix(".net"))
        elif format == "pickle":
            nx.write_gpickle(self.G, path.with_suffix(".gpickle"))
        else:
            raise ValueError(f"Unsupported format: {format}")

def main():
    # Create graph and load data
    graph = ConceptGraph()
    graph.load_from_json("/Users/mollyhan/PycharmProjects/Cognitext/data/entity_analysis_results.json")

    # Print basic statistics
    print("\nGraph Statistics:")
    graph.print_graph_stats()

    # Print central concepts
    print("\nMost Central Concepts:")
    central_concepts = graph.get_central_concepts(5)
    for concept, centrality in central_concepts:
        print(f"- {concept}: {centrality:.3f}")

    # Print related concepts for the most frequent concept
    most_frequent = max(graph.G.nodes(data=True),
                        key=lambda x: x[1]['frequency'])[0]
    print(f"\nConcepts related to '{most_frequent}':")
    related = graph.get_related_concepts(most_frequent)
    for r in related[:5]:
        print(f"- {r['concept']}: {r['weight']} shared paragraphs")

    # Visualize the graph
    print("\nGenerating visualization...")
    graph.visualize_top_concepts(top_n=15)
    graph.save_graph("/Users/mollyhan/PycharmProjects/Cognitext/visualizations/sample_graph_top15", format="gexf")

if __name__ == "__main__":
    main()