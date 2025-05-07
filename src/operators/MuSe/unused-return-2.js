const Mutation = require('../../mutation');

function UR1Operator() {
    this.ID = "UR1";
    this.name = "unused-return-1";
}

UR1Operator.prototype.getMutations = function(file, source, visit) {
    const mutations = [];

    visit({
        FunctionDefinition: (functionNode) => {
            const functionStart = functionNode.range[0];
            const functionEnd = functionNode.range[1] + 1;

            const originalFunctionCode = source.slice(functionStart, functionEnd);
            let modifiedFunctionCode = originalFunctionCode;
            let hasMutations = false;

            const initializations = new Set();

            // Primo passo: raccogli tutte le inizializzazioni (dichiarazioni con assegnazioni)
            visit({
                VariableDeclarationStatement: (node) => {
                    if (node.initialValue && (node.initialValue.type === 'FunctionCall' || node.initialValue.type === 'MemberAccess')) {
                        initializations.add(node.range[0]);
                    }
                }
            });

            // Secondo passo: muta solo assegnazioni che NON sono inizializzazioni
            visit({
                ExpressionStatement: (stmt) => {
                    const expression = stmt.expression;
                    if (
                        expression.type &&
                        expression.type === 'BinaryOperation' &&
                        expression.operator === '=' &&
                        (expression.right.type === 'FunctionCall' || expression.right.type === 'MemberAccess') &&
                        expression.right.memberName !== 'sender'
                    ) {
                        const start = stmt.range[0];
                        const end = stmt.range[1] + 1;

                        // Se questa è un'inizializzazione, la saltiamo
                        if (initializations.has(start)) return;

                        const original = source.slice(start, end);
                        const mutated = source.slice(expression.right.range[0], expression.right.range[1] + 1) + ";";

                        modifiedFunctionCode = modifiedFunctionCode.replace(original, mutated);
                        hasMutations = true;
                    }
                }
            });

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

module.exports = UR1Operator;
