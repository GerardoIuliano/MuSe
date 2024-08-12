const Mutation = require('../../../mutation');

function AODOperator() {
    this.ID = "AOD";
    this.name = "arithmetic-operation-duplication";
}

AODOperator.prototype.getMutations = function(file, source, visit) {
    const mutations = [];

    visit({
        BinaryExpression: (node) => {
            // Identifica le operazioni aritmetiche
            const isArithmetic = ['+', '-', '*', '/'].includes(node.operator);
            if (isArithmetic) {
                const start = node.range[0];
                const end = node.range[1];
                const startLine = node.loc.start.line;
                const endLine = node.loc.end.line;
                const original = source.slice(start, end);

                // Duplica l'operazione aritmetica
                const duplicatedOperation = `(${original}) ${node.operator} (${original})`;

                const replacement = source.substring(0, start) + duplicatedOperation + source.substring(end);

                mutations.push(new Mutation(file, start, end, startLine, endLine, original, replacement, this.ID));
            }
        },
        CallExpression: (node) => {
            // Identifica le operazioni SafeMath (add, sub, mul, div)
            const isSafeMath = ['add', 'sub', 'mul', 'div'].includes(node.callee.property.name);
            if (isSafeMath) {
                const start = node.range[0];
                const end = node.range[1];
                const startLine = node.loc.start.line;
                const endLine = node.loc.end.line;
                const original = source.slice(start, end);

                // Duplica l'operazione SafeMath
                const duplicatedOperation = `${original}, ${original}`;

                const replacement = source.substring(0, start) + duplicatedOperation + source.substring(end);

                mutations.push(new Mutation(file, start, end, startLine, endLine, original, replacement, this.ID));
            }
        }
    });

    return mutations;
};

module.exports = AODOperator;
