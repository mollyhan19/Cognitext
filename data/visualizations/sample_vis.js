import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import _ from 'lodash';

const relationColors = {
  IsA: '#4299E1',        // Blue
  PartOf: '#48BB78',     // Green
  UsedFor: '#ED8936',    // Orange
  CapableOf: '#9F7AEA',  // Purple
  Causes: '#F56565',     // Red
  HasProperty: '#ECC94B', // Yellow
  LocatedNear: '#4FD1C5', // Teal
  DerivedFrom: '#ED64A6'  // Pink
};

const ConceptGraph = () => {
  const [relations, setRelations] = useState([
    {
      source: "algorithm",
      relation_type: "IsA",
      target: "sequence of instructions",
      evidence: "An algorithm is a step-by-step procedure for calculations."
    },
    {
      source: "algorithm",
      relation_type: "CapableOf",
      target: "solving problems",
      evidence: "Algorithms are designed to solve specific computational problems."
    },
    {
      source: "time complexity",
      relation_type: "PartOf",
      target: "algorithm analysis",
      evidence: "Time complexity is a key aspect of analyzing algorithms."
    }
  ]);

  // Group relations by source concept
  const groupedByConcept = _.groupBy(relations, 'source');

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>Concept Relationship Graph</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="mb-4">
          <h3 className="text-lg font-semibold mb-2">Relation Types Legend</h3>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(relationColors).map(([type, color]) => (
              <div key={type} className="flex items-center">
                <div
                  className="w-4 h-4 rounded mr-2"
                  style={{ backgroundColor: color }}
                />
                <span>{type}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-6">
          {Object.entries(groupedByConcept).map(([concept, rels]) => (
            <div key={concept} className="border rounded-lg p-4">
              <h3 className="text-xl font-bold mb-3">{concept}</h3>
              <div className="space-y-2">
                {rels.map((rel, idx) => (
                  <div key={idx} className="flex items-center space-x-2">
                    <div
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: relationColors[rel.relation_type] }}
                    />
                    <span className="text-sm font-medium" style={{ color: relationColors[rel.relation_type] }}>
                      {rel.relation_type}
                    </span>
                    <span className="text-gray-600">→</span>
                    <span className="font-medium">{rel.target}</span>
                  </div>
                ))}
              </div>
              <div className="mt-2 text-sm text-gray-500">
                {rels.map((rel, idx) => (
                  <div key={idx} className="mt-1">
                    <span className="font-medium">Evidence:</span> {rel.evidence}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};

export default ConceptGraph;