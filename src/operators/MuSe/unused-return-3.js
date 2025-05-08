const Mutation = require('../../mutation');

function UR3Operator() {
    this.ID = "UR3";
    this.name = "unused-return-3";
}

UR3Operator.prototype.getMutations = function(file, source, visit) {
    const mutations = [];

    visit({
        FunctionDefinition: (functionNode) => {
            const functionStart = functionNode.range[0];
            const functionEnd = functionNode.range[1] + 1;

            // Estrai il codice originale della funzione
            const originalFunctionCode = source.slice(functionStart, functionEnd);
            let modifiedFunctionCode = originalFunctionCode;
            let hasMutations = false;

            visit({
                BinaryOperation: (node) => {
                    const start = node.range[0];
                    const end = node.range[1] + 1;

                    if (start >= functionStart && end <= functionEnd && node.operator === '=' &&
                        (node.right.type === 'FunctionCall' || node.right.type === 'MemberAccess') &&
                        node.right.memberName !== 'sender'
                    ) {
                        // Rimuovi l'assegnazione dall'originale
                        const original = source.slice(start, end);
                        const mutatedString = original.replace(/^[^=]+=\s*/, "");

                        // Aggiorna il codice della funzione con la modifica
                        modifiedFunctionCode = modifiedFunctionCode.replace(original, mutatedString);
                        hasMutations = true;
                    }
                },
            });

            // Se sono state fatte modifiche, crea una mutazione per l'intera funzione
            if (hasMutations) {
                const startLine = functionNode.loc.start.line;
                const endLine = functionNode.loc.end.line;

                mutations.push(
                    new Mutation(file, functionStart, functionEnd, startLine, endLine, originalFunctionCode, modifiedFunctionCode, this.ID)
                );
            }
        }
    });

    return mutations;
};

module.exports = UR3Operator;