from pymodbus.client import ModbusTcpClient
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy.lang import Builder

# Carrega o arquivo KV
Builder.load_file('temperaturas.kv')

class LeitorTemperaturasModbus:
    """
    Classe responsável exclusiva pela comunicação Modbus com os sensores de temperatura.
    """
    def __init__(self, host='10.15.30.181', port=502):
        self.client = ModbusTcpClient(host, port=port)
        self.conectado = False

    def conectar(self):
        self.conectado = self.client.connect()
        return self.conectado

    def desconectar(self):
        self.client.close()
        self.conectado = False

    def ler_temperaturas(self):
        """
        Lê os registradores de 700 a 707 (8 registradores no total) 
        para capturar os 4 valores de 32-bits (FP).
        """
        if not self.conectado:
            return None

        try:
            resposta = self.client.read_holding_registers(700, 8)
            if resposta.isError():
                return None

            regs = self.client.convert_from_registers(
                resposta.registers,
            )

            raw_r = self.client.convert_from_registers(regs[0:2], data_type=self.client.DATATYPE.INT32)
            temp_r = raw_r / 10.0
            raw_s = self.client.convert_from_registers(regs[2:4], data_type=self.client.DATATYPE.INT32)
            temp_s = raw_s / 10.0
            raw_t = self.client.convert_from_registers(regs[4:6], data_type=self.client.DATATYPE.INT32)
            temp_t = raw_t / 10.0
            raw_carc = self.client.convert_from_registers(regs[6:8], data_type=self.client.DATATYPE.INT32)
            temp_carc = raw_carc / 10.0

            return {
                "temp_r": temp_r,
                "temp_s": temp_s,
                "temp_t": temp_t,
                "temp_carc": temp_carc
            }
        except Exception as e:
            print(f"Erro na leitura Modbus: {e}")
            return None

class PainelTemperaturas(BoxLayout):
    """
    Classe de Interface Gráfica Kivy para exibição das temperaturas.
    """
    def __init__(self, leitor_modbus, **kwargs):
        super(PainelTemperaturas, self).__init__(**kwargs)
        self.leitor = leitor_modbus

    def iniciar_atualizacao(self, intervalo=1.0):
        # Tenta conectar e agenda a atualização periódica
        if self.leitor.conectar():
            self.ids.lbl_status.text = "Status: Conectado"
            self.ids.lbl_status.color = (0, 1, 0, 1)
        else:
            self.ids.lbl_status.text = "Status: Falha na Conexão Modbus"
            self.ids.lbl_status.color = (1, 0, 0, 1)

        Clock.schedule_interval(self.atualizar_dados, intervalo)

    def atualizar_dados(self, dt):
        dados = self.leitor.ler_temperaturas()
        if dados:
            # Atualiza as labels usando os IDs definidos no arquivo .kv
            self.ids.lbl_temp_r.text = f"Temp Enrolamento R: {dados['temp_r']:.1f} °C"
            self.ids.lbl_temp_s.text = f"Temp Enrolamento S: {dados['temp_s']:.1f} °C"
            self.ids.lbl_temp_t.text = f"Temp Enrolamento T: {dados['temp_t']:.1f} °C"
            self.ids.lbl_temp_carc.text = f"Temp Carcaça: {dados['temp_carc']:.1f} °C"
            self.ids.lbl_status.text = "Status: Conectado e Lendo"
            self.ids.lbl_status.color = (0, 1, 0, 1)
        else:
            self.ids.lbl_status.text = "Status: Falha na Leitura (Dados Desatualizados)"
            self.ids.lbl_status.color = (1, 0, 0, 1)

class SistemaSupervisorioApp(App):
    """
    App principal.
    """
    def build(self):
        leitor = LeitorTemperaturasModbus(host='10.15.30.181', port=502)
        painel = PainelTemperaturas(leitor_modbus=leitor)
        painel.iniciar_atualizacao(intervalo=1.0)
        return painel

if __name__ == '__main__':
    SistemaSupervisorioApp().run()