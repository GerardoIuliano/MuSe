const Mutation = require('../../mutation');

function DTUOperator() {
  this.ID = "DTU";
  this.name = "delegatecall-to-untrusted";
}

DTUOperator.prototype.getMutations = function(file, source, visit) {
  const mutations = [];

  visit({

    ContractDefinition: (node) => {
      if (node.kind === 'interface'|| node.kind === 'library') {
        return;
      }

      if (!node.subNodes || node.subNodes.length === 0) {
        return; // Salta il contratto se non ha subNodes
      }
      
      // Otteniamo l'inizio e la fine del contratto
      const contractStart = node.subNodes[0].range[0];
      const contractEnd = node.range[1]; // Fine del contratto

      // A questo punto, dobbiamo visitare le espressioni all'interno del contratto
      let hasDelegateCall = false;

      visit({

        VariableDeclarationStatement: (node) => {
          if (node.initialValue && containsDelegateCall(node.initialValue)) {
            hasDelegateCall = true;
          }
        },

        ExpressionStatement: (exprNode) => {
          // Verifica che il nodo sia valido e abbia la proprietà `range`
          if (exprNode && exprNode.range) {
            const exprStart = exprNode.range[0];
            const exprEnd = exprNode.range[1];

            // Controlla se l'espressione è contenuta nel range del contratto
            if (exprStart >= contractStart && exprEnd <= contractEnd && containsDelegateCall(exprNode)) {
              hasDelegateCall = true; // Segna che abbiamo trovato una delegatecall
            }
          }
        },
      });


      if (hasDelegateCall) {
        const startLine = node.loc.start.line;
        const endLine = node.loc.end.line;

        // Aggiunta di `address delegate;` e `setDelegate` all'inizio del contratto
        const originalContractCode = source.slice(contractStart, contractEnd);
        const mutatedCode = 
          `address public delegate;\n` +
          `function setDelegate(address _delegate) public { delegate = _delegate; }\n` +
          originalContractCode
          .replace(/(\b\w+)(\.delegate)?\.delegatecall/g, 'delegate.delegatecall') // Gestione altri delegatecall, senza duplicati
          .replace(/address\(this\)\.delegatecall\((.*?)\)/g, 'delegate.delegatecall($1)')
          .replace(/require\s*\(\s*(?:address\(this\)\.)?delegate(\.delegate)?\.delegatecall/g, 'require(delegate.delegatecall') // Modifica per require
          .replace(/\bbetokenLogic(\.delegate)?\.delegatecall/g, 'delegate.delegatecall'); // Modifica per `betokenLogic.delegatecall`


        // Crea una sola mutazione
        mutations.push(new Mutation(file, contractStart, contractEnd, startLine, endLine, originalContractCode, mutatedCode, this.ID));
      }
    },
  });

  return mutations;
};

// Funzione di supporto per verificare se ci sono delegatecall
function containsDelegateCall(node) {
  if (!node) return false;

  // Controlla se il nodo è una delegatecall
  if (node.memberName === 'delegatecall') {
    return true;
  }

  if(node.type === 'BinaryOperation'){
    return containsDelegateCall(node.right);
  }

  // Controlla se uno degli argomenti contiene una delegatecall
  if (node.arguments && node.arguments.some(arg => containsDelegateCall(arg))) {
    return true;
  }

  // Ricorsione per controllare l'espressione
  return node.expression ? containsDelegateCall(node.expression) : false;
}

module.exports = DTUOperator;
