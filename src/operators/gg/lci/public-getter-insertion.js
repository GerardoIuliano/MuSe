const Mutation = require('../../../mutation');

function PGIOperator() {
    this.ID = "PGI";
    this.name = "public-getter-insertion";
}

PGIOperator.prototype.getMutations = function(file, source, visit) {
    const mutations = [];
    
    visit({
        VariableDeclarator: (node) => {
            if (node.id && node.id.name && node.init) {
                const varName = node.id.name;
                const visibility = getVariableVisibility(node);
                
                if (visibility === 'private' || visibility === 'internal') {
                    const start = node.range[0];
                    const end = node.range[1];
                    const startLine = node.loc.start.line;
                    const endLine = node.loc.end.line;
                    const original = source.slice(start, end);

                    // Creazione della funzione getter pubblica
                    const getterFunction = `
                        function get${capitalize(varName)}() public view returns (${getType(node)}) {
                            return ${varName};
                        }
                    `;
                    
                    const replacement = source.substring(0, end) + getterFunction + source.substring(end);

                    mutations.push(new Mutation(file, start, end, startLine, endLine, original, replacement, this.ID));
                }
            }
        }
    });

    return mutations;
};

// Helper functions
function getVariableVisibility(node) {
    // Logic to determine visibility (placeholder)
    return 'private'; // Placeholder, should be implemented based on context
}

function getType(node) {
    // Logic to determine type (placeholder)
    return 'uint256'; // Placeholder, should be implemented based on context
}

function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

module.exports = PGIOperator;
