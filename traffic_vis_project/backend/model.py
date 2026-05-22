import torch
import torch.nn as nn

class BaselineTrafficModel(nn.Module):
    """
    Un modelo base simple (MLP/Linear) que toma una ventana de tiempo histórica
    y predice la velocidad futura para todos los sensores.
    """
    def __init__(self, num_nodes=325, history_len=12, predict_len=12):
        super(BaselineTrafficModel, self).__init__()
        self.num_nodes = num_nodes
        self.history_len = history_len
        self.predict_len = predict_len
        
        self.linear = nn.Linear(history_len, predict_len)
        
    def forward(self, x):
        """
        x shape: (batch_size, num_nodes, history_len)
        returns: (batch_size, num_nodes, predict_len)
        """
        out = self.linear(x)
        return out

def get_untrained_model(num_nodes=325):
    """Retorna el modelo instanciado. En el futuro aquí cargaríamos los pesos .pt"""
    model = BaselineTrafficModel(num_nodes=num_nodes, history_len=12, predict_len=12)
    model.eval() # Modo inferencia
    return model
