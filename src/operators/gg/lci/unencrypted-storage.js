const Mutation = require('../../../mutation');

function USOperator() {
    this.ID = "US";
    this.name = "unencrypted-storage";
}

USOperator.prototype.getMutations = function(file, source, visit) {
    const mutations = [];
    
    visit({
        CallExpression: (node) => {
            if (node.callee.name === 'encrypt') {
                const start = node.range[0];
                const end = node.range[1];
                const startLine = node.loc.start.line;
                const endLine = node.loc.end.line;
                const original = source.slice(start, end);

                // Sostituzione della funzione di crittografia con memorizzazione diretta
                const replacement = source.substring(0, start) + 'data' + source.substring(end); // Direct storage replacement

                mutations.push(new Mutation(file, start, end, startLine, endLine, original, replacement, this.ID));
            }
        }
    });

    return mutations;
};

module.exports = USOperator;
