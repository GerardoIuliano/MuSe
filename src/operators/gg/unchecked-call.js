const Mutation = require('../../mutation');

function UCOperator() {
    this.ID = "UC";
    this.name = "unchecked-call";
}

UCOperator.prototype.getMutations = function(file, source, visit) {
    const mutations = [];

    const isSendOrCall = (node) => {
        if (!node) return false;
        return node.type === 'MemberAccess' &&  (node.memberName === 'call');
    }

    // Funzione per controllare se un nodo contiene chiamate a `send`, `call` o `transfer`
    const requireContainsSendOrCall = (node) => {
        // Funzione ricorsiva per controllare le espressioni
        const checkExpression = (expr) => {
            if (!expr) return false;
    
            if (expr.type === 'MemberAccess' && 
                ['call'].includes(expr.memberName)) {
                const start = node.range[0];
                const end = node.range[1];
                return true;
            }

            if(node.type === 'UnaryOperation'){
                return checkExpression(node.subExpression);
            }
    
            if (node.type === 'BinaryOperation') {
                return checkExpression(node.right);
            }
    
            // Se l'espressione ha un membro, controlla ricorsivamente
            if (expr.expression) {
                return checkExpression(expr.expression);
            }
    
            return false;
        };

        // Controlla se il tipo di dichiarazione è ExpressionStatement
        if (node.type === 'ExpressionStatement' &&
            node.expression.type === 'FunctionCall' &&
            (node.expression.expression.name === 'require' || node.expression.expression.name === 'assert')
        ) {
            return node.expression.arguments.some(arg => {
                if(arg.type === "UnaryOperation"){
                    return checkExpression(arg.subExpression);
                }
                return checkExpression(arg);
            });
        }
        return false;
    };
    

    visit({
        ExpressionStatement: (node) => {
            if (requireContainsSendOrCall(node)) {
                const start = node.range[0];
                const end = node.range[1];
                const startLine = node.loc.start.line;
                const endLine = node.loc.end.line;
                const original = source.slice(start, end);

                let mutatedString = original
                    .replace(/^require\s*\(\s*!?\s*/, '')
                    .replace(/^assert\s*\(\s*!?\s*/, '')
                    .replace(/\s*\)\s*;?$/, '');
                
                // Rimuove tutto dalla virgola successiva all'ultimo ")" fino a ";" finale
                const lastClosingParenIndex = mutatedString.lastIndexOf(')');
                const commaIndex = mutatedString.indexOf(',', lastClosingParenIndex);
                if (commaIndex !== -1) {
                    mutatedString = mutatedString.slice(0, commaIndex).trim();
                }

                mutations.push(new Mutation(file, start, end, startLine, endLine, original, mutatedString, this.ID));
            }
        },
        IfStatement: (node) => {
            const condition = node.condition;

            if ((condition.expression && isSendOrCall(condition.expression)) || (condition.subExpression && condition.subExpression.expression && isSendOrCall(condition.subExpression.expression))) {
                const start = node.range[0];
                const end = node.range[1] +1;
                const startLine = node.loc.start.line;
                const endLine = node.loc.end.line;
                const original = source.slice(start, end);

                const callExpression = condition.expression ? source.slice(condition.range[0], condition.range[1] + 1) : source.slice(condition.subExpression.range[0], condition.subExpression.range[1] + 1);

                const hasBraces = original.includes("{");
                const hasElse = source.slice(end).trim().startsWith("else");

                let mutatedString;

                const cleanedOriginal = original
                    .replace(/\bthrow\s*;\s*/g, '') // Rimuove `throw;` anche con spazi extra o invisibili
                    .replace(/\brevert\s*;\s*/g, '') // Rimuove `revert;` con eventuali spazi extra
                    .trim(); // Rimuove gli spazi bianchi prima e dopo

                if (hasBraces) {
                    // Se ci sono le parentesi graffe, modifica normalmente
                    mutatedString = `if (true) { ${callExpression}; ${cleanedOriginal.slice(cleanedOriginal.indexOf("{") + 1, cleanedOriginal.lastIndexOf("}") + 1).trim()}`;
                    if (hasElse) {
                        mutatedString += "}";  // Aggiungi la graffa solo se non c'è un `else`
                    }
                } else {
                    const expressionAfterIf = cleanedOriginal.slice(cleanedOriginal.indexOf(")") + 2).trim();
                    mutatedString = `if (true) { ${callExpression}; ${expressionAfterIf} }`;
                }

                mutations.push(new Mutation(file, start, end, startLine, endLine, original, mutatedString, this.ID));
            }
        }
    });

    return mutations;
};

module.exports = UCOperator;
