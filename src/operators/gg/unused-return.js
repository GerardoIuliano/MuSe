const Mutation = require('../../mutation');

function UROperator() {
    this.ID = "UR";
    this.name = "unused-return";
}

UROperator.prototype.getMutations = function(file, source, visit) {
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

                    if (start >= functionStart && end <= functionEnd && node.operator === '=' && (node.right.type === 'FunctionCall' || node.right.type === 'MemberAccess')) {
                        // Rimuovi l'assegnazione dall'originale
                        const original = source.slice(start, end);
                        const mutatedString = original.replace(/^[^=]+=\s*/, "");

                        // Aggiorna il codice della funzione con la modifica
                        modifiedFunctionCode = modifiedFunctionCode.replace(original, mutatedString);
                        hasMutations = true;
                    }
                },

                VariableDeclarationStatement:(node) => {
                    const start = node.range[0];
                    const end = node.range[1] + 1;

                    if (start >= functionStart && end <= functionEnd && node.variables[0] && 
                        (node.variables[0].typeName.name === 'uint256' || node.variables[0].typeName.name === 'uint')) {
                        const original = source.slice(start, end);

                        // Identifica il contenuto della funzione chiamata (senza ridefinire la variabile)
                        const declarationMatch = original.match(/(uint(?:256)?\s+\w+\s*=\s*)([^;]+);/);
                        if (declarationMatch) {
                            const variableDeclaration = declarationMatch[1]; // Parte iniziale fino al "="
                            const functionCall = declarationMatch[2];       // Parte dopo il "=" fino al ";"

                            // Mutazione: assegna 0 alla variabile e lascia la chiamata a parte
                            const mutatedString = `${variableDeclaration}0; ${functionCall};`;

                            // Aggiorna il codice della funzione con la modifica
                            modifiedFunctionCode = modifiedFunctionCode.replace(original, mutatedString);
                            hasMutations = true;
                        }
                    }
                }
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

module.exports = UROperator;
