const Mutation = require('../../mutation');

function IUOOperator() {
  this.ID = "IUO";
  this.name = "integer-underflow-overflow";
}

// Funzione helper per confrontare due versioni semantiche.
function isVersionLessThan(current, target) {
  const currentParts = current.split('.').map(Number);
  const targetParts = target.split('.').map(Number);
  for (let i = 0; i < Math.max(currentParts.length, targetParts.length); i++) {
    const c = currentParts[i] || 0;
    const t = targetParts[i] || 0;
    if (c < t) return true;
    if (c > t) return false;
  }
  return false;
}

// Funzione esterna che controlla se il contratto ha una versione inferiore a 0.8.18.
function isContractVersionEligible(source) {
  const pragmaRegex = /pragma solidity\s+([^;]+);/;
  const pragmaMatch = source.match(pragmaRegex);
  if (pragmaMatch) {
    const versionString = pragmaMatch[1];
    const versionMatch = versionString.match(/(\d+\.\d+\.\d+)/);
    if (versionMatch) {
      const versionNumber = versionMatch[1];
      return isVersionLessThan(versionNumber, "0.8.18");
    }
  }
  return false;
}

IUOOperator.prototype.getMutations = function(file, source, visit) {
  const mutations = [];

  // Caso Solidity < 0.8.18: sostituisce le chiamate a SafeMath
  if (isContractVersionEligible(source)) {
    const safeMathMapping = {
      "add": "+",
      "sub": "-",
      "mul": "*",
      "div": "/",
      "mod": "%"
    };

    visit({
      FunctionCall: (node) => {
        if (
          node.expression &&
          node.expression.type === "MemberAccess" &&
          safeMathMapping.hasOwnProperty(node.expression.memberName)
        ) {
          if (node.arguments && node.arguments.length === 1) {
            const operatorSymbol = safeMathMapping[node.expression.memberName];
            const leftNode = node.expression.expression;
            const rightNode = node.arguments[0];
            const leftText = source.slice(leftNode.range[0], leftNode.range[1] + 1);
            const rightText = source.slice(rightNode.range[0], rightNode.range[1] + 1);
            const replacement = `${leftText} ${operatorSymbol} ${rightText}`;
            const start = node.range[0];
            const end = node.range[1] + 1;
            const original = source.slice(start, end);
            mutations.push(new Mutation(file, start, end, node.loc.start.line, node.loc.end.line, original, replacement, this.ID));
          }
        }
      }
    });
  } else {
    // Caso Solidity >= 0.8.18:

    // 1. Gestione delle dichiarazioni con inizializzazione contenente un'operazione binaria.
    visit({
      VariableDeclarationStatement: (node) => {
        if (
          node.initialValue &&
          node.initialValue.type === "BinaryOperation" &&
          ["+", "-", "*", "/", "%"].includes(node.initialValue.operator)
        ) {
          // Supponiamo che ci sia una sola dichiarazione in questo statement.
          const varName = node.variables[0].name;
          // Estraiamo il testo originale dello statement.
          const original = source.slice(node.range[0], node.range[1] + 1);
          // Utilizziamo una regex per suddividere la dichiarazione dall'inizializzazione.
          // La regex cerca: tutto fino al nome della variabile, eventuali spazi, "=" e poi il resto fino al ";".
          const splitRegex = new RegExp(`(.*\\b${varName}\\b\\s*)(=\\s*)(.*);`);
          const match = original.match(splitRegex);
          if (match) {
            const declarationPart = match[1].trim(); // es. "uint256 c"
            const initializationPart = match[3].trim(); // es. "a + b"
            const replacement = `${declarationPart}; unchecked { ${varName} = ${initializationPart}; }`;
            mutations.push(new Mutation(file, node.range[0], node.range[1] + 1,
              node.loc.start.line, node.loc.end.line, original, replacement, this.ID));
          }
        }
      }
    });

    // 2. Gestione delle operazioni binarie isolate.
    visit({
      // Controllo su =: l'rvalue deve contenere un'operazione aritmetica
      // Se l'rvalue non è una binary operation o se il suo operatore non è aritmetico, non effettuo la mutazione.
      BinaryOperation: (node) => {
        if( (node.operator === "=" &&
            (node.right &&
            node.right.type === "BinaryOperation" &&
            ["+", "-", "*", "/", "%"].includes(node.right.operator))) ||
            (node.operator === "+=" || node.operator === "-=" || node.operator === "*=" || node.operator === "/=" || node.operator === "%=")
        ) {

          // Ottengo l'intera riga in cui è contenuta la BinaryOperation.
          const lines = source.split('\n');
          const lineNumber = node.loc.start.line;
          const lineText = lines[lineNumber - 1];
          // Se la riga contiene costrutti in cui "unchecked" non può essere usato, salto la mutazione.
          if (/\b(require|if|while|for)\s*\(/.test(lineText)) {
            return;
          }

          let original = source.slice(node.range[0], node.range[1] + 2).trim();
          const replacement = `unchecked { ${original} }`;
          mutations.push(new Mutation(
            file,
            node.range[0],
            node.range[1] + 2,
            node.loc.start.line,
            node.loc.end.line,
            source.slice(node.range[0], node.range[1] + 2),
            replacement,
            this.ID
          ));
        }
      }
    });
  }

  return mutations;
};

module.exports = IUOOperator;
