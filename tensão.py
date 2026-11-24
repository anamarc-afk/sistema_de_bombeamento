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
        self.grafico_atual = "tensão"
        self.configurar_grafico()
        self.configurar_modbus()
        
        # Adiciona o gráfico ao container definido no bancada.kv
        self.mostrar_grafico_tensao()
        
        # Inicia a rotina de leitura do CLP a cada 1.0 segundo
        # Inicia a rotina que vai DISPARAR a leitura em segundo plano
        self.evento_leitura = Clock.schedule_interval(self.disparar_leitura, 1.0)

    def configurar_grafico(self):
        """Prepara o layout do Matplotlib e converte para Widget Kivy"""
        self.max_pontos = 100
        self.dados_rs = collections.deque(maxlen=self.max_pontos)
        self.dados_st = collections.deque(maxlen=self.max_pontos)
        self.dados_tr = collections.deque(maxlen=self.max_pontos)
        self.dados_media = collections.deque(maxlen=self.max_pontos)
        self.dados_crs = collections.deque(maxlen=self.max_pontos)
        self.dados_cst = collections.deque(maxlen=self.max_pontos)
        self.dados_ctr = collections.deque(maxlen=self.max_pontos)
        self.dados_cns = collections.deque(maxlen=self.max_pontos)
        self.dados_cmt = collections.deque(maxlen=self.max_pontos)
        self.tempo = collections.deque(maxlen=self.max_pontos)
        self.contador = 0

        # Criação da Figura
        self.fig, self.ax = plt.subplots(figsize=(8, 5))
        self.fig.patch.set_facecolor('#E0E0E0') 
        self.ax.set_facecolor('#F5F5F5')

        self.linha_rs, = self.ax.plot([], [], label='Tensão RS', color='#2E86C1', linewidth=2)
        self.linha_st, = self.ax.plot([], [], label='Tensão ST', color='#28B463', linewidth=2)
        self.linha_tr, = self.ax.plot([], [], label='Tensão TR', color='#884EA0', linewidth=2)
        self.linha_media, = self.ax.plot([], [], label='Média Tensão', color='#D35400', linewidth=2, linestyle='--')

        self.ax.set_title("Tendência de Tensões", fontsize=12)
        self.ax.set_xlabel("Leituras")
        self.ax.set_ylabel("Tensão (V)")
        self.ax.legend(loc='upper right')
        self.ax.grid(True, linestyle='--', alpha=0.6)
        
        # Conversão vitalícia: transforma o plot num Widget do Kivy
        self.canvas_kivy = FigureCanvasKivyAgg(self.fig)

        self.fig_corrente, self.ax_corrente = plt.subplots(figsize=(8, 5))
        self.fig_corrente.patch.set_facecolor('#E0E0E0') 
        self.ax_corrente.set_facecolor('#F5F5F5')
        
        self.linha_crs, = self.ax_corrente.plot([], [], label='Corrente RS', color="#2E86C186", linewidth=2)
        self.linha_cst, = self.ax_corrente.plot([], [], label='Corrente ST', color="#28B46281", linewidth=2)
        self.linha_ctr, = self.ax_corrente.plot([], [], label='Corrente TR', color="#874EA073", linewidth=2)
        self.linha_cns, = self.ax_corrente.plot([], [], label='Corrente N', color="#000000", linewidth=2)
        self.linha_cmt, = self.ax_corrente.plot([], [], label='Média Corrente', color="#E7FC2A", linewidth=2, linestyle='--')

        self.ax_corrente.set_title("Tendência de Corrente", fontsize=12)
        self.ax_corrente.set_xlabel("Leituras")
        self.ax_corrente.set_ylabel("Corrente (A)")
        self.ax_corrente.legend(loc='upper right')
        self.ax_corrente.grid(True, linestyle='--', alpha=0.6)
        
        # Conversão vitalícia: transforma o plot num Widget do Kivy
        self.canvas_corrente = FigureCanvasKivyAgg(self.fig_corrente)

    def mostrar_grafico_tensao(self):
        self.grafico_atual = "tensao"
        container = self.root.ids.graph_container
        if self.canvas_kivy.parent:
            self.canvas_kivy.parent.remove_widget(self.canvas_kivy)
        container.clear_widgets()
        container.add_widget(self.canvas_kivy)
        self.canvas_kivy.draw_idle()

    def mostrar_grafico_corrente(self):
        self.grafico_atual = "corrente"
        container = self.root.ids.graph_container
        if self.canvas_corrente.parent:
            self.canvas_corrente.parent.remove_widget(self.canvas_corrente)
        container.clear_widgets()
        container.add_widget(self.canvas_corrente)
        self.canvas_corrente.draw_idle()

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
                resposta = self.client.read_holding_registers(address=840, count=10, slave=1)
                
                if not resposta.isError():
                    c_rs = resposta.registers[0] / 10.0
                    c_st = resposta.registers[1] / 10.0
                    c_tr = resposta.registers[2] / 10.0
                    c_ns = resposta.registers[3] / 10.0
                    c_mt = resposta.registers[5] / 10.0
                    v_rs = resposta.registers[7] / 10.0
                    v_st = resposta.registers[8] / 10.0
                    v_tr = resposta.registers[9] / 10.0
                    
                    # Envia os dados de volta para a Thread Principal para atualizar a tela
                    self.atualizar_grafico(c_rs, c_st, c_tr, c_ns, c_mt, v_rs, v_st, v_tr)
        except Exception as e:
            print(f"Falha de comunicação Modbus: {e}")

    @mainthread
    def atualizar_grafico(self, c_rs, c_st, c_tr, c_ns, c_mt, v_rs, v_st, v_tr):
        """3. Roda na Thread Principal. Apenas injeta os números e redesenha."""
        v_media = (v_rs + v_st + v_tr) / 3.0

        self.contador += 1
        self.tempo.append(self.contador)
        self.dados_crs.append(c_rs)
        self.dados_cst.append(c_st)
        self.dados_ctr.append(c_tr)
        self.dados_cns.append(c_ns)
        self.dados_cmt.append(c_mt)
        self.dados_rs.append(v_rs)
        self.dados_st.append(v_st)
        self.dados_tr.append(v_tr)
        self.dados_media.append(v_media)

        x_min = max(0, self.contador - self.max_pontos)
        x_max = self.contador + 5
        
        self.linha_crs.set_data(self.tempo, self.dados_crs)
        self.linha_cst.set_data(self.tempo, self.dados_cst)
        self.linha_ctr.set_data(self.tempo, self.dados_ctr)
        self.linha_cns.set_data(self.tempo, self.dados_cns)
        self.linha_cmt.set_data(self.tempo, self.dados_cmt)
        valores_c = (
            list(self.dados_crs) + list(self.dados_cst) +
            list(self.dados_ctr) + list(self.dados_cns) + list(self.dados_cmt)
        )
        if valores_c:
            self.ax_corrente.set_ylim(max(0, min(valores_c) - 2), max(valores_c) + 2)

        self.linha_rs.set_data(self.tempo, self.dados_rs)
        self.linha_st.set_data(self.tempo, self.dados_st)
        self.linha_tr.set_data(self.tempo, self.dados_tr)
        self.linha_media.set_data(self.tempo, self.dados_media)
        valores_v = list(self.dados_rs) + list(self.dados_st) + list(self.dados_tr)
        if valores_v:
            self.ax_tensao.set_ylim(min(valores_v) - 10, max(valores_v) + 10)

        if self.grafico_atual == "tensao":
            self.canvas_kivy.draw_idle()
        else:
            self.canvas_corrente.draw_idle()

    def on_stop(self):
        """Garante o encerramento seguro ao fechar o App"""
        if self.evento_leitura:
            self.evento_leitura.cancel()
        if hasattr(self, 'client'):
            self.client.close()

if __name__ == '__main__':
    BaseApp().run()