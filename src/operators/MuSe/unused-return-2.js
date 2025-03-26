const Mutation = require('../../mutation');

function UR2Operator() {
    this.ID = "UR2";
    this.name = "unused-return-2";
}

UR2Operator.prototype.getMutations = function(file, source, visit) {
    const mutations = [];

    function hasFunctionCall(node) {
        if (node.type && node.type === "FunctionCall") {
            return true;
        }
        if (node.type && node.type === "BinaryOperation") {
            return (
                (node.left && hasFunctionCall(node.left)) ||
                (node.right && hasFunctionCall(node.right))
            );
        }
        return false;
    }

    function getDefaultValue(typeName) {
        if (/^uint\d*$/.test(typeName) || /^int\d*$/.test(typeName)) {
            return '0'; // Copre tutti i uintX e intX (es. uint8, uint16, int128)
        }
        switch (typeName) {
            case 'bool':
                return 'false';
            case 'string':
                return '""';
            case 'address':
                return 'address(0)';
            default:
                return '0'; // Default fallback
        }
    }

    visit({
        FunctionDefinition: (functionNode) => {
            const functionStart = functionNode.range[0];
            const functionEnd = functionNode.range[1] + 1;
            const originalFunctionCode = source.slice(functionStart, functionEnd);
            let modifiedFunctionCode = originalFunctionCode;
            let hasMutations = false;

            visit({
                VariableDeclarationStatement: (node) => {
                    const start = node.range[0];
                    const end = node.range[1] + 1;

                    if (start >= functionStart && end <= functionEnd &&
                        node.initialValue &&
                        hasFunctionCall(node.initialValue) &&
                        node.variables[0] && node.variables[0].typeName && node.variables[0].typeName.name
                    ) {
                        const original = source.slice(start, end);
                        const declarationMatch = original.match(/(\w+\s+\w+)\s*=\s*([^;]+);/);

                        if (declarationMatch) {
                            const variableTypeAndName = declarationMatch[1];
                            const functionCall = declarationMatch[2];
                            const typeName = node.variables[0].typeName.name;
                            const defaultValue = getDefaultValue(typeName);

                            // Assegna un valore predefinito alla variabile e lascia la chiamata a parte
                            const mutatedString = `${variableTypeAndName} = ${defaultValue}; ${functionCall};`;

                            modifiedFunctionCode = modifiedFunctionCode.replace(original, mutatedString);
                            hasMutations = true;
                        }
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

module.exports = UR2Operator;
