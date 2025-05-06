const Mutation = require('../../mutation');

function IUOOperator() {
    this.ID = "IUO";
    this.name = "integer-underflow-overflow";
}

function isVersionLessThan(current, target) {
    const c = current.split('.').map(Number);
    const t = target.split('.').map(Number);
    for (let i = 0; i < 3; i++) {
        if ((c[i] || 0) < (t[i] || 0)) return true;
        if ((c[i] || 0) > (t[i] || 0)) return false;
    }
    return false;
}

function isContractVersionEligible(source) {
    const match = source.match(/pragma solidity\s+([^;]+);/);
    if (match) {
        const version = (match[1].match(/(\d+\.\d+\.\d+)/) || [])[1];
        if (version) return isVersionLessThan(version, "0.8.18");
    }
    return false;
}

function extractText(node, source) {
    if (!node) return "<?>";

    switch (node.type) {
        case 'Identifier':
            return node.name;
        case 'Literal':
            return String(node.value);
        case 'NumberLiteral':
            return node.number;
        case 'IndexAccess':
            return `${extractText(node.base, source)}[${extractText(node.index, source)}]`;
        case 'MemberAccess':
            return `${extractText(node.expression, source)}.${node.memberName}`;
        case 'BinaryOperation':
            return `(${extractText(node.left, source)} ${node.operator} ${extractText(node.right, source)})`;
        case 'FunctionCall':
            const args = (node.arguments || []).map(arg => extractText(arg, source)).join(", ");
            return `${extractText(node.expression, source)}(${args})`;
        default:
            if (node.range && node.range[0] !== node.range[1]) {
                return source.slice(node.range[0], node.range[1]);
            }
            return "<?>";
    }
}

function printLeftExpression(node) {
    if (!node) return "<?>";

    switch (node.type) {
        case 'Identifier':
            return node.name;
        case 'IndexAccess':
            return `${printLeftExpression(node.base)}[${printLeftExpression(node.index)}]`;
        case 'MemberAccess':
            return `${printLeftExpression(node.expression)}.${node.memberName}`;
        default:
            return "<?>";
    }
}

function fixParentheses(str) {
    let result = '';
    let balance = 0;
    for (const char of str) {
        if (char === '(') balance++;
        else if (char === ')') {
            if (balance > 0) balance--;
            else continue;
        }
        result += char;
    }
    result += ')'.repeat(balance);
    return result;
}

function maybeStripFinalSemicolon(str, isOldVersion) {
    if (!isOldVersion) return str;
    return str.replace(/;\s*$/, '');
}

IUOOperator.prototype.getMutations = function (file, source, visit) {
    const mutations = [];
    const isOldVersion = isContractVersionEligible(source);

    const safeMathMethods = {
        add: '+',
        sub: '-',
        mul: '*',
        div: '/',
        mod: '%',
    };

    function isSafeMathCall(node) {
        return node &&
            node.type === 'FunctionCall' &&
            node.expression &&
            node.expression.type === 'MemberAccess' &&
            safeMathMethods.hasOwnProperty(node.expression.memberName) &&
            extractText(node.expression.expression, source) !== "SafeMath";
    }

    function transformSafeMath(node) {
        if (isSafeMathCall(node)) {
            const operator = safeMathMethods[node.expression.memberName];
            const args = node.arguments;
            if (!args || args.length < 1) return extractText(node, source);

            const left = node.expression.expression;
            const right = args[0];

            const leftStr = (left.type === 'FunctionCall' && left.expression && typeof left.expression.name === 'string')
                ? `${left.expression.name}(${(left.arguments || []).map(arg => transformSafeMath(arg)).join(', ')})`
                : transformSafeMath(left);

            const rightStr = transformSafeMath(right);

            return `(${leftStr} ${operator} ${rightStr})`;
        }

        if (node.type === 'BinaryOperation') {
            return `${transformSafeMath(node.left)} ${node.operator} ${transformSafeMath(node.right)}`;
        }

        return extractText(node, source);
    }

    function containsSafeMath(node) {
        if (!node) return false;
        if (isSafeMathCall(node)) return true;
        if (Array.isArray(node.arguments) && node.arguments.some(containsSafeMath)) return true;
        if (node.left && containsSafeMath(node.left)) return true;
        if (node.right && containsSafeMath(node.right)) return true;
        if (node.expression && containsSafeMath(node.expression)) return true;
        return false;
    }

    if (isOldVersion) {
        function mutateSafeMathExpression(node, type) {
            if (!node || !node.range || !node.loc) return;

            let expression = null;

            if (type === 'ReturnStatement') expression = node.expression;
            else if (type === 'ExpressionStatement') expression = node.expression;
            else if (type === 'Assignment') expression = node.right;
            else if (type === 'VariableDeclarationStatement') expression = node.initialValue;

            if (!expression || !containsSafeMath(expression)) return;

            if (
                expression.type === 'FunctionCall' &&
                expression.expression &&
                (
                    expression.expression.name === 'require' ||
                    expression.expression.name === 'approve'
                )
            ) {
                return;
            }

            const original = source.slice(node.range[0], node.range[1]);
            let mutatedInner = transformSafeMath(expression);
            mutatedInner = fixParentheses(mutatedInner);

            let mutated;

            switch (type) {
                case 'ReturnStatement':
                    mutated = maybeStripFinalSemicolon(`return ${mutatedInner};`, isOldVersion);
                    break;
                case 'ExpressionStatement':
                    mutated = maybeStripFinalSemicolon(`${mutatedInner};`, isOldVersion);
                    break;
                case 'Assignment': {
                    const leftText = printLeftExpression(node.left);
                    mutated = maybeStripFinalSemicolon(`${leftText} = ${mutatedInner}`, isOldVersion);
                    break;
                }
                case 'VariableDeclarationStatement':
                    if (node.declarations && node.declarations.length > 0) {
                        const decl = node.declarations[0];
                        const name = decl.name || decl.id || 'var';
                        const typeName = extractText(decl.typeName, source);
                        mutated = maybeStripFinalSemicolon(`${typeName} ${name} = ${mutatedInner}`, isOldVersion);
                    } else return;
                    break;
                default:
                    return;
            }

            mutations.push(new Mutation(
                file,
                node.range[0],
                node.range[1],
                node.loc.start.line,
                node.loc.end.line,
                original,
                mutated,
                "IUO"
            ));
        }

        visit({
            ExpressionStatement: function (node) {
                mutateSafeMathExpression.call(this, node, 'ExpressionStatement');
            },
            ReturnStatement: function (node) {
                mutateSafeMathExpression.call(this, node, 'ReturnStatement');
            },
            VariableDeclarationStatement: function (node) {
                mutateSafeMathExpression.call(this, node, 'VariableDeclarationStatement');
            },
            Assignment: function (node) {
                mutateSafeMathExpression.call(this, node, 'Assignment');
            }
        });
    }

    if (!isOldVersion) {
        const isArithmeticOp = (op) =>
            ["+", "-", "*", "/", "%", "+=", "-=", "*=", "/=", "%="].includes(op);

        function wrapInUnchecked(text) {
            const body = text.trim().replace(/;+\s*$/, '');
            return `unchecked { ${body}; }`;
        }

        function nodeContainsArithmetic(node) {
            if (!node || typeof node !== 'object') return false;

            if (
                (node.type === "Assignment" && isArithmeticOp(node.operator)) ||
                (node.type === "BinaryOperation" && isArithmeticOp(node.operator))
            ) {
                return true;
            }

            const fields = ['left', 'right', 'expression', 'initialValue', 'body'];

            for (const field of fields) {
                if (
                    node[field] &&
                    typeof node[field] === 'object' &&
                    nodeContainsArithmetic(node[field])
                ) return true;
            }

            if (
                node.type === 'FunctionCall' &&
                Array.isArray(node.arguments) &&
                node.arguments.some(arg => nodeContainsArithmetic(arg))
            ) return true;

            return false;
        }

        visit({
            ExpressionStatement: (node) => {
                if (!node || !node.expression || !node.range || !node.loc) return;

                const expr = node.expression;

                if (
                    expr &&
                    expr.type === 'FunctionCall' &&
                    expr.expression &&
                    (expr.expression.name === 'require' || expr.expression.name === 'assert')
                ) return;

                if (!nodeContainsArithmetic(expr)) return;

                const fullText = source.slice(node.range[0], node.range[1] + 1);
                const cleaned = wrapInUnchecked(fullText);

                mutations.push(new Mutation(
                    file,
                    node.range[0],
                    node.range[1] + 1,
                    node.loc.start.line,
                    node.loc.end.line,
                    fullText,
                    cleaned,
                    this.ID
                ));
            }
        });
    }

    return mutations;
};

module.exports = IUOOperator;
