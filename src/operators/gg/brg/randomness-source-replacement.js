const Mutation = require('../../../mutation');

function RSROperator() {
    this.ID = "RSR";
    this.name = "randomness-source-replacement";
}

RSROperator.prototype.getMutations = function(file, source, visit) {
    const mutations = [];
    
    visit({
        MemberExpression: (node) => {
            if (node.object.name === 'block' && 
                (node.property.name === 'timestamp' || node.property.name === 'difficulty')) {

                const start = node.range[0];
                const end = node.range[1];
                const startLine = node.loc.start.line;
                const endLine = node.loc.end.line;
                const original = source.slice(start, end);

                // Create replacements with fixed or predictable values
                let replacement;
                if (node.property.name === 'timestamp') {
                    replacement = source.substring(0, start) + "0x5c7b4e3f" + source.substring(end); // Fixed timestamp value
                } else if (node.property.name === 'difficulty') {
                    replacement = source.substring(0, start) + "0x7b9f8e1d" + source.substring(end); // Fixed difficulty value
                }

                mutations.push(new Mutation(file, start, end, startLine, endLine, original, replacement, this.ID));
            }
        },
        CallExpression: (node) => {
            if (node.callee.name === 'keccak256') {
                // If used in conjunction with randomness sources
                const args = node.arguments;
                args.forEach((arg) => {
                    if (arg.type === 'BinaryExpression' && arg.left.object.name === 'block' &&
                        (arg.left.property.name === 'timestamp' || arg.left.property.name === 'difficulty')) {
                        
                        const start = arg.range[0];
                        const end = arg.range[1];
                        const startLine = arg.loc.start.line;
                        const endLine = arg.loc.end.line;
                        const original = source.slice(start, end);
                        
                        // Replace entire keccak256 with a fixed value
                        const replacement = source.substring(0, start) + "0x1234567890abcdef" + source.substring(end); // Fixed value

                        mutations.push(new Mutation(file, start, end, startLine, endLine, original, replacement, this.ID));
                    }
                });
            }
        }
    });

    return mutations;
};

module.exports = RSROperator;
