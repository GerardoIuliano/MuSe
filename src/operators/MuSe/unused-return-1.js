const Mutation = require('../../mutation');

function UR1Operator() {
    this.ID = "UR1";
    this.name = "unused-return-1";
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
            return null;
    }
}

UR1Operator.prototype.getMutations = function(file, source, visit) {
    const mutations = [];
    const variableTypes = {};

    // Prima passata: raccogli dichiarazioni variabili
    visit({
        VariableDeclaration: (node) => {
            if (node.name && node.typeName) {
                const varName = node.name;
                variableTypes[varName] = source.slice(node.typeName.range[0], node.typeName.range[1] + 1);
            }
        }
    });

    // Seconda passata: mutazioni
    visit({
        ExpressionStatement: (node) => {
            const expr = node.expression;

            if (
                expr &&
                expr.type === 'BinaryOperation' &&
                expr.operator === '=' &&
                expr.right &&
                expr.right.type === 'FunctionCall'
            ) {
                const start = node.range[0];
                const end = node.range[1];
                const original = source.slice(start, end);
                const rhs = source.slice(expr.right.range[0], expr.right.range[1]+1);

                if (expr.left.type === 'Identifier') {
                    const varName = expr.left.name;
                    const typeName = variableTypes[varName];
                    if (!typeName) return;
                    const defaultValue = getDefaultValue(typeName.trim());
                    if (defaultValue === null) return;

                    const lhs = source.slice(expr.left.range[0], expr.left.range[1]+1);
                    const mutatedString = `${lhs} = ${defaultValue}; ${rhs}`;
                    mutations.push(new Mutation(file, start, end, node.loc.start.line, node.loc.end.line, original, mutatedString, this.ID));

                } else if (expr.left.type === 'TupleExpression') {
                    const elements = expr.left.components;
                    let allDefaults = [];
                    for (let i = 0; i < elements.length; i++) {
                        const el = elements[i];
                        if (!el || el.type !== 'Identifier') continue;

                        const varName = el.name;
                        const typeName = variableTypes[varName];
                        if (!typeName) return;

                        const defaultValue = getDefaultValue(typeName.trim());
                        if (defaultValue === null) return;

                        allDefaults.push(`${varName} = ${defaultValue}`);
                    }

                    if (allDefaults.length === 0) return;

                    const mutatedString = `${allDefaults.join('; ')}; ${rhs}`;
                    mutations.push(new Mutation(file, start, end, node.loc.start.line, node.loc.end.line, original, mutatedString, this.ID));
                }
            }
        }
    });

    return mutations;
};

module.exports = UR1Operator;