import inspect
import threading
from kivymd.app import MDApp
from kivymd.uix.button import MDFlatButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.boxlayout import MDBoxLayout
from kivy.properties import StringProperty
from kivy.clock import Clock, mainthread
from kivy.lang import Builder
from pymodbus.client import ModbusTcpClient

MODBUS_MODO = "TCP"  # "TCP" ou "RTU"

# Configurações Modbus TCP
TCP_HOST = "10.15.30.181"
TCP_PORT = 502

# Configurações Modbus RTU (se MODBUS_MODO == "RTU")
RTU_PORT = "/dev/ttyUSB0"  # Ex.: "COM3" no Windows
RTU_BAUDRATE = 9600
RTU_PARITY = "N"  # "N", "E", "O"
RTU_STOPBITS = 1
RTU_BYTESIZE = 8

# Endereçamento das tensões RS, ST, TR
REGISTRO_INICIAL = 847
QTD_REGISTRADORES = 3
SLAVE_ID = 1
DIVISOR_TENSAO = 10.0  # Ex.: 3805 -> 380.5 V

# Classe que controla os dados dentro da janela
class JanelaTensoesContent(MDBoxLayout):
    tensao_rs = StringProperty("0.0")
    tensao_st = StringProperty("0.0")
    tensao_tr = StringProperty("0.0")
    media = StringProperty("0.0")

class MeuSupervisorio(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dialog_tensoes = None
        self.conteudo_tensoes = None
        self.evento_atualizacao = None
        self.lendo_modbus = False
        self.cliente_modbus = None
        self._modbus_lock = threading.Lock()

    def build(self):
        # Carrega o seu arquivo base.kv
        return Builder.load_file("base.kv")

    # Esta função roda automaticamente assim que o aplicativo inicia
    def on_start(self):
        self.abrir_janela_tensoes()

    def on_stop(self):
        if self.evento_atualizacao:
            self.evento_atualizacao.cancel()
        with self._modbus_lock:
            if self.cliente_modbus:
                self.cliente_modbus.close()

    def _criar_cliente_modbus(self):
        if MODBUS_MODO.upper() == "RTU":
            # Descomente o import de ModbusSerialClient acima para usar RTU
            raise RuntimeError(
                "Importe ModbusSerialClient e configure os parâmetros RTU para usar MODBUS_MODO='RTU'."
            )
        return ModbusTcpClient(host=TCP_HOST, port=TCP_PORT, timeout=2.0)

    def _ler_holding_registers(self, address: int, count: int, slave: int):
        """
        Compatível com variações de assinatura entre versões do pymodbus (slave / unit / device_id).
        """
        read_fn = self.cliente_modbus.read_holding_registers
        params = inspect.signature(read_fn).parameters
        kwargs = {}
        if "slave" in params:
            kwargs["slave"] = slave
        elif "device_id" in params:
            kwargs["device_id"] = slave
        elif "unit" in params:
            kwargs["unit"] = slave

        try:
            return read_fn(address, count=count, **kwargs)
        except TypeError:
            # Fallback posicional caso a assinatura use argumentos posicionais
            return read_fn(address, count, slave)

    def abrir_janela_tensoes(self):
        # Cria a janela apenas uma vez para economizar memória
        if not self.dialog_tensoes:
            self.conteudo_tensoes = JanelaTensoesContent()
            self.dialog_tensoes = MDDialog(
                title="Valores Atuais das Tensões",
                type="custom",
                content_cls=self.conteudo_tensoes,
                buttons=[
                    MDFlatButton(
                        text="FECHAR",
                        on_release=lambda *args: self.fechar_janela_tensoes(),
                    ),
                ],
            )
            self.dialog_tensoes.bind(on_dismiss=self.dispensar_dialogo)
        
        self.dialog_tensoes.open()
        # Dispara uma leitura imediata e mantém o ciclo a cada 1 segundo
        self.agendar_leitura_modbus()
        if not self.evento_atualizacao:
            self.evento_atualizacao = Clock.schedule_interval(
                self.agendar_leitura_modbus, 1.0)

    def dispensar_dialogo(self, *args):
        if self.evento_atualizacao:
            self.evento_atualizacao.cancel()
            self.evento_atualizacao = None

    def fechar_janela_tensoes(self, *args):
        if self.dialog_tensoes:
            self.dialog_tensoes.dismiss()

    def agendar_leitura_modbus(self, *args):
        if self.lendo_modbus:
            return
        self.lendo_modbus = True
        threading.Thread(target=self._worker_modbus, daemon=True).start()

    def _worker_modbus(self):
        try:
            with self._modbus_lock:
                if not self.cliente_modbus.connected:
                    if not self.cliente_modbus.connect():
                        raise ConnectionError("Não foi possível conectar ao dispositivo Modbus.")

                resposta = self._ler_holding_registers(
                    address=REGISTRO_INICIAL,
                    count=QTD_REGISTRADORES,
                    slave=SLAVE_ID,
                )

            if resposta.isError():
                raise RuntimeError(f"Resposta de erro Modbus: {resposta}")

            regs = resposta.registers
            if len(regs) < 3:
                raise ValueError(f"Registradores insuficientes recebidos: {regs}")

            rs = regs[0] / DIVISOR_TENSAO
            st = regs[1] / DIVISOR_TENSAO
            tr = regs[2] / DIVISOR_TENSAO
            media = (rs + st + tr)/3.0

            self._atualizar_ui(rs, st, tr, media)

        except Exception as erro:
            print(f"[Modbus] Falha na leitura: {erro}")
            with self._modbus_lock:
                if self.cliente_modbus:
                    self.cliente_modbus.close()
        finally:
            self.lendo_modbus = False

    @mainthread
    def _atualizar_ui(self, rs: float, st: float, tr: float, media: float):
            if not self.dialog_tensoes or not self.conteudo_tensoes:
                return
            self.conteudo_tensoes.tensao_rs = f"{rs:.1f}"
            self.conteudo_tensoes.tensao_st = f"{st:.1f}"
            self.conteudo_tensoes.tensao_tr = f"{tr:.1f}"
            self.conteudo_tensoes.media = f"{media:.1f}"

if __name__ == "__main__":
    MeuSupervisorio().run()