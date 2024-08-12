const Mutation = require('../../../mutation');

function GLOperator() {
    this.ID = "GL";
    this.name = "gas-limitation";
}

GLOperator.prototype.getMutations = function(file, source, visit) {
    const mutations = [];

    visit({
        CallExpression: (node) => {
            if (isExternalCall(node)) {
                const start = node.range[0];
                const end = node.range[1];
                const startLine = node.loc.start.line;
                const endLine = node.loc.end.line;
                const original = source.slice(start, end);

                // Inserimento del limite di gas
                const limitedGasCall = original.replace(/\b(call|delegatecall|staticcall)\b/g, `$1{gas: 10000}`);

                const replacement = source.substring(0, start) + limitedGasCall + source.substring(end);

                mutations.push(new Mutation(file, start, end, startLine, endLine, original, replacement, this.ID));
            }
        }
    });

    return mutations;
};

function isExternalCall(node) {
    // Placeholder logic to determine if it's an external call
    return node.callee && node.callee.property && ['call', 'delegatecall', 'staticcall'].includes(node.callee.property.name);
}

module.exports = GLOperator;
