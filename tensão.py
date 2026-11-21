import collections
import threading
import matplotlib.pyplot as plt
from pymodbus.client import ModbusTcpClient

from kivy.clock import Clock, mainthread
from kivy.clock import Clock
from kivy.lang import Builder
from kivymd.app import MDApp
from kivy_garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg

class BaseApp(MDApp):
    def build(self):
        # Configuração visual do KivyMD (ISA-101 recomenda cores neutras)
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "Gray"
        
        # Carrega a interface do arquivo .kv
        return Builder.load_file('base.kv')

    def on_start(self):
        """Executado assim que o aplicativo inicia a tela"""
        self.configurar_grafico()
        self.configurar_modbus()
        
        # Adiciona o gráfico ao container definido no bancada.kv
        self.root.ids.graph_container.add_widget(self.canvas_kivy)
        
        # Inicia a rotina de leitura do CLP a cada 1.0 segundo
        # Inicia a rotina que vai DISPARAR a leitura em segundo plano
        self.evento_leitura = Clock.schedule_interval(self.disparar_leitura, 1.0)

    def configurar_grafico(self):
        """Prepara o layout do Matplotlib e converte para Widget Kivy"""
        self.max_pontos = 100
        self.dados_rs = collections.deque(maxlen=self.max_pontos)
        self.dados_st = collections.deque(maxlen=self.max_pontos)
        self.dados_tr = collections.deque(maxlen=self.max_pontos)
        self.tempo = collections.deque(maxlen=self.max_pontos)
        self.contador = 0

        # Criação da Figura
        self.fig, self.ax = plt.subplots(figsize=(8, 5))
        self.fig.patch.set_facecolor('#E0E0E0') 
        self.ax.set_facecolor('#F5F5F5')

        self.linha_rs, = self.ax.plot([], [], label='Tensão RS', color='#2E86C1', linewidth=2)
        self.linha_st, = self.ax.plot([], [], label='Tensão ST', color='#28B463', linewidth=2)
        self.linha_tr, = self.ax.plot([], [], label='Tensão TR', color='#884EA0', linewidth=2)

        self.ax.set_title("Tendência de Tensões", fontsize=12)
        self.ax.set_xlabel("Leituras")
        self.ax.set_ylabel("Tensão (V)")
        self.ax.legend(loc='upper right')
        self.ax.grid(True, linestyle='--', alpha=0.6)
        
        # Conversão vitalícia: transforma o plot num Widget do Kivy
        self.canvas_kivy = FigureCanvasKivyAgg(self.fig)

    def configurar_modbus(self):
        """Inicializa o cliente Modbus TCP"""
        IP_BANCADA = '10.15.30.181'
        PORTA = 502
        self.client = ModbusTcpClient(IP_BANCADA, port=PORTA)

    def disparar_leitura(self, dt):
        """1. Chamada pelo Clock. Apenas cria uma tarefa em segundo plano e liberta o Kivy imediatamente."""
        threading.Thread(target=self.tarefa_leitura_modbus, daemon=True).start()

    def tarefa_leitura_modbus(self):
        """2. Roda em segundo plano. Não trava a interface se a rede demorar."""
        try:
            if self.client.connect():
                resposta = self.client.read_holding_registers(address=847, count=3, slave=1)
                
                if not resposta.isError():
                    v_rs = resposta.registers[0] / 10.0
                    v_st = resposta.registers[1] / 10.0
                    v_tr = resposta.registers[2] / 10.0
                    
                    # Envia os dados de volta para a Thread Principal para atualizar a tela
                    self.atualizar_grafico(v_rs, v_st, v_tr)
        except Exception as e:
            print(f"Falha de comunicação Modbus: {e}")

    @mainthread
    def atualizar_grafico(self, v_rs, v_st, v_tr):
        """3. Roda na Thread Principal. Apenas injeta os números e redesenha."""
        self.contador += 1
        self.tempo.append(self.contador)
        self.dados_rs.append(v_rs)
        self.dados_st.append(v_st)
        self.dados_tr.append(v_tr)
        
        self.linha_rs.set_data(self.tempo, self.dados_rs)
        self.linha_st.set_data(self.tempo, self.dados_st)
        self.linha_tr.set_data(self.tempo, self.dados_tr)
        
        self.ax.set_xlim(max(0, self.contador - self.max_pontos), self.contador + 5)
        
        todos_valores = list(self.dados_rs) + list(self.dados_st) + list(self.dados_tr)
        if todos_valores:
            self.ax.set_ylim(min(todos_valores) - 10, max(todos_valores) + 10)
        
        # draw_idle pede ao Kivy para redesenhar o gráfico "quando tiver um tempo livre"
        # Isso evita que o Kivy engasgue se estiver a mover a janela naquele exato milissegundo.
        self.canvas_kivy.draw_idle()

    def on_stop(self):
        """Garante o encerramento seguro ao fechar o App"""
        if self.evento_leitura:
            self.evento_leitura.cancel()
        if hasattr(self, 'client'):
            self.client.close()

if __name__ == '__main__':
    BaseApp().run()