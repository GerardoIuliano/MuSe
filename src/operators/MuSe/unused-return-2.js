const Mutation = require('../../mutation');

function UR2Operator() {
    this.ID = "UR2";
    this.name = "unused-return-2";
}

UR2Operator.prototype.getMutations = function(file, source, visit) {
    const mutations = [];

    function hasFunctionCall(node) {
        if (!node) return false;
        if (node.type === "FunctionCall") return true;
        if (node.type === "BinaryOperation") {
            return hasFunctionCall(node.left) || hasFunctionCall(node.right);
        }
        return false;
    }

    function getDefaultValue(typeName) {
        if (/^uint\d*$/.test(typeName) || /^int\d*$/.test(typeName)) {
            return '0';
        }
        if (/^bytes\d+$/.test(typeName)) {
            return '0';
        }
        switch (typeName) {
            case 'bytes':
                return 'new bytes(0)';
            case 'bool':
                return 'false';
            case 'string':
                return '""';
            case 'address':
                return 'address(0)';
            default:
                return null; // tipo non gestito => nessuna mutazione
        }
    }

    function reconstructType(typeNode, fallbackStorageLocation) {
        if (!typeNode) return 'unknown';

        if (typeNode.type === "ArrayTypeName") {
            const baseType = reconstructType(typeNode.baseTypeName);
            const storage = typeNode.storageLocation || fallbackStorageLocation || '';
            return `${baseType}[]${storage ? ' ' + storage : ''}`;
        }

        if (typeNode.type === "UserDefinedTypeName" && typeNode.namePath) {
            const storage = typeNode.storageLocation || fallbackStorageLocation || '';
            return `${typeNode.namePath}${storage ? ' ' + storage : ''}`.trim();
        }

        let typeStr = "";
        if (typeNode.name) {
            typeStr = typeNode.name;
        } else if (typeNode.type === "ElementaryTypeName") {
            typeStr = typeNode.name;
        }

        const storage = typeNode.storageLocation || fallbackStorageLocation || '';
        return `${typeStr}${storage ? ' ' + storage : ''}`.trim();
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

                    if (
                        start >= functionStart && end <= functionEnd &&
                        node.initialValue &&
                        hasFunctionCall(node.initialValue)
                    ) {
                        // Evita di mutare se la chiamata contiene la parola 'payable'
                        const functionCallCode = source.slice(node.initialValue.range[0], node.initialValue.range[1] + 1);
                        if (/\bpayable\b/.test(functionCallCode)) return;

                        const declaredVariables = node.variables.filter(v => v !== null);
                        if (declaredVariables.length !== 1) return;

                        const variable = declaredVariables[0];
                        if (!variable || !variable.name || !variable.typeName) return;

                        // Salta se il tipo è un array
                        if (variable.typeName.type === "ArrayTypeName") return;

                        const original = source.slice(start, end);
                        const varName = variable.name;
                        const fullType = reconstructType(variable.typeName, variable.storageLocation);
                        const simpleTypeName = fullType.split(/[ \[]/)[0];
                        const defaultValue = getDefaultValue(simpleTypeName);

                        // Salta se il tipo non è supportato
                        if (defaultValue === null) return;

                        const mutatedString = `${fullType} ${varName} = ${defaultValue}; ${source.slice(node.initialValue.range[0], node.initialValue.range[1] + 1)};`;

                        modifiedFunctionCode = modifiedFunctionCode.replace(original, mutatedString);
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

module.exports = UR2Operator;
