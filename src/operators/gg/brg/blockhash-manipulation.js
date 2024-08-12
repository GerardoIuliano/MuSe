const Mutation = require('../../../mutation');

function BMOperator() {
    this.ID = "BM";
    this.name = "blockhash-manipulation";
}

BMOperator.prototype.getMutations = function(file, source, visit) {
    const mutations = [];

    visit({
        // Look for occurrences of blockhash
        MemberExpression: (node) => {
            if (node.object.name === 'blockhash' && node.property.name === 'blockhash') {
                const start = node.range[0];
                const end = node.range[1];
                const startLine = node.loc.start.line;
                const endLine = node.loc.end.line;
                const original = source.slice(start, end);
                
                // Create replacements with the fixed blockhash value
                const replacement = source.substring(0, start) + `0x3f5b76c4f3c3e9d49bb8a4ef5d90a047eb95e7b2e0b9b6363f4f7d4fce0f7ab2` + source.substring(end);
                
                mutations.push(new Mutation(file, start, end, startLine, endLine, original, replacement, this.ID));
            }
        }
    });

    return mutations;
};

module.exports = BMOperator;
