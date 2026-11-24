import inspect
import threading
from kivymd.app import MDApp
from kivymd.uix.button import MDFlatButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.boxlayout import MDBoxLayout
from kivy.properties import StringProperty, ListProperty
from kivy.clock import Clock, mainthread
from kivy.lang import Builder
from pymodbus.client import ModbusTcpClient

MODBUS_MODO = "TCP"  # "TCP" ou "RTU"

# Configurações Modbus TCP - Bancada de Bombeamento
TCP_HOST = "10.15.30.181"
TCP_PORT = 502
SLAVE_ID = 1
AMBIENTE_ATIVO = "CLP Bombeamento"  # Altere para "Simulador Local" se usar 127.0.0.1

# Mapeamento de registradores (4X - Holding Registers) e divisores
REG_TENSOES_INICIO = 847      # 847: RS, 848: ST, 849: TR (Div: 10)
QTD_TENSOES = 3
DIV_TENSAO = 10.0

REG_CORRENTES_INICIO = 840    # 840: R, 841: S, 842: T, 843: N, 845: Média (Div: 10)
QTD_CORRENTES = 6
DIV_CORRENTE = 10.0

REG_DEMANDA_INICIO = 1204     # 1204: Ant, 1205: Atual, 1206: Méd, 1207: Pico, 1208: Prev (Div: 10)
QTD_DEMANDA = 5
DIV_DEMANDA = 10.0

REG_FP_INICIO = 868           # 868: R, 869: S, 870: T, 871: Total (Div: 1000)
QTD_FP = 4
DIV_FP = 1000.0


# --- Classes de conteúdo das 4 janelas (MDDialog) ---

class JanelaTensoesContent(MDBoxLayout):
    tensao_rs = StringProperty("--.-")
    tensao_st = StringProperty("--.-")
    tensao_tr = StringProperty("--.-")
    media = StringProperty("--.-")
    status_dados = StringProperty("Aguardando leitura...")


class JanelaCorrentesContent(MDBoxLayout):
    corrente_r = StringProperty("--.-")
    corrente_s = StringProperty("--.-")
    corrente_t = StringProperty("--.-")
    corrente_n = StringProperty("--.-")
    corrente_media = StringProperty("--.-")
    status_dados = StringProperty("Aguardando leitura...")


class JanelaDemandaContent(MDBoxLayout):
    demanda_anterior = StringProperty("--.-")
    demanda_atual = StringProperty("--.-")
    demanda_media = StringProperty("--.-")
    demanda_pico = StringProperty("--.-")
    demanda_prevista = StringProperty("--.-")
    status_dados = StringProperty("Aguardando leitura...")


class JanelaFatorPotenciaContent(MDBoxLayout):
    fp_r = StringProperty("-.---")
    fp_s = StringProperty("-.---")
    fp_t = StringProperty("-.---")
    fp_total = StringProperty("-.---")
    status_dados = StringProperty("Aguardando leitura...")


class MeuSupervisorio(MDApp):
    # Propriedades para o cabeçalho de status (ISA-101 / HP-HMI)
    ambiente_texto = StringProperty(f"Ambiente: {AMBIENTE_ATIVO} ({TCP_HOST}:{TCP_PORT})")
    status_comm_texto = StringProperty("COMUNICAÇÃO: AGUARDANDO")
    status_comm_icone = StringProperty("lan-pending")
    status_comm_cor = ListProperty([0.35, 0.35, 0.35, 1])  # Cinza neutro (normal/espera)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dialogs = {}
        self.conteudos = {}
        self.janela_ativa = None  # "tensoes", "correntes", "demanda" ou "fp"

        self.evento_atualizacao = None
        self.lendo_modbus = False
        self.cliente_modbus = None
        self._modbus_lock = threading.Lock()

    def build(self):
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "BlueGray"
        return Builder.load_file("base.kv")

    def on_start(self):
        # Inicializa o cliente Modbus TCP sem travar a interface
        self.cliente_modbus = self._criar_cliente_modbus()

    def on_stop(self):
        if self.evento_atualizacao:
            self.evento_atualizacao.cancel()
        with self._modbus_lock:
            if self.cliente_modbus:
                self.cliente_modbus.close()

    def _criar_cliente_modbus(self):
        if MODBUS_MODO.upper() == "RTU":
            raise RuntimeError(
                "Importe ModbusSerialClient e configure os parâmetros RTU para usar MODBUS_MODO='RTU'."
            )
        return ModbusTcpClient(host=TCP_HOST, port=TCP_PORT, timeout=2.0)

    def _ler_holding_registers(self, address: int, count: int, slave: int):
        """Compatível com variações de assinatura entre versões do pymodbus."""
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
            return read_fn(address, count, slave)

    # --- Abertura das 4 janelas pelos botões ---

    def abrir_janela_tensoes(self):
        self._abrir_janela("tensoes", "Tensões da Rede (V)", JanelaTensoesContent)

    def abrir_janela_correntes(self):
        self._abrir_janela("correntes", "Correntes do Motor (A)", JanelaCorrentesContent)

    def abrir_janela_demanda(self):
        self._abrir_janela("demanda", "Demanda Registrada do Motor (kW)", JanelaDemandaContent)

    def abrir_janela_fp(self):
        self._abrir_janela("fp", "Fator de Potência do Motor", JanelaFatorPotenciaContent)

    def _abrir_janela(self, chave: str, titulo: str, classe_conteudo):
        if chave not in self.dialogs:
            conteudo = classe_conteudo()
            dialog = MDDialog(
                title=titulo,
                type="custom",
                content_cls=conteudo,
                md_bg_color=[0.91, 0.91, 0.91, 1],  # Cinza neutro HP-HMI
                buttons=[
                    MDFlatButton(
                        text="FECHAR",
                        theme_text_color="Custom",
                        text_color=[0.2, 0.2, 0.2, 1],
                        on_release=lambda *args, c=chave: self.fechar_janela(c),
                    ),
                ],
            )
            dialog.bind(on_dismiss=self.dispensar_dialogo)
            self.conteudos[chave] = conteudo
            self.dialogs[chave] = dialog

        self.janela_ativa = chave
        self.dialogs[chave].open()

        # Dispara leitura imediata e mantém atualização periódica (1s)
        self.agendar_leitura_modbus()
        if not self.evento_atualizacao:
            self.evento_atualizacao = Clock.schedule_interval(self.agendar_leitura_modbus, 1.0)

    def fechar_janela(self, chave: str):
        if chave in self.dialogs:
            self.dialogs[chave].dismiss()

    def dispensar_dialogo(self, *args):
        self.janela_ativa = None
        if self.evento_atualizacao:
            self.evento_atualizacao.cancel()
            self.evento_atualizacao = None

    # --- Aquisição Modbus em segundo plano ---

    def agendar_leitura_modbus(self, *args):
        if self.lendo_modbus or not self.janela_ativa:
            return
        self.lendo_modbus = True
        janela = self.janela_ativa
        threading.Thread(target=self._worker_modbus, args=(janela,), daemon=True).start()

    def _worker_modbus(self, janela: str):
        try:
            with self._modbus_lock:
                if self.cliente_modbus is None:
                    self.cliente_modbus = self._criar_cliente_modbus()

                if not self.cliente_modbus.connected:
                    if not self.cliente_modbus.connect():
                        raise ConnectionError("Sem conexão com o servidor Modbus TCP.")

                if janela == "tensoes":
                    resp = self._ler_holding_registers(REG_TENSOES_INICIO, QTD_TENSOES, SLAVE_ID)
                elif janela == "correntes":
                    resp = self._ler_holding_registers(REG_CORRENTES_INICIO, QTD_CORRENTES, SLAVE_ID)
                elif janela == "demanda":
                    resp = self._ler_holding_registers(REG_DEMANDA_INICIO, QTD_DEMANDA, SLAVE_ID)
                elif janela == "fp":
                    resp = self._ler_holding_registers(REG_FP_INICIO, QTD_FP, SLAVE_ID)
                else:
                    return

            if resp.isError():
                raise RuntimeError(f"Erro Modbus: {resp}")

            regs = resp.registers
            self._atualizar_status_comm(conectado=True)

            if janela == "tensoes" and len(regs) >= 3:
                rs = regs[0] / DIV_TENSAO
                st = regs[1] / DIV_TENSAO
                tr = regs[2] / DIV_TENSAO
                media = (rs + st + tr) / 3.0
                self._atualizar_ui_tensoes(rs, st, tr, media)

            elif janela == "correntes" and len(regs) >= 6:
                ir = regs[0] / DIV_CORRENTE
                is_ = regs[1] / DIV_CORRENTE
                it = regs[2] / DIV_CORRENTE
                in_ = regs[3] / DIV_CORRENTE
                imedia = regs[5] / DIV_CORRENTE  # Endereço 845
                self._atualizar_ui_correntes(ir, is_, it, in_, imedia)

            elif janela == "demanda" and len(regs) >= 5:
                d_ant = regs[0] / DIV_DEMANDA
                d_atu = regs[1] / DIV_DEMANDA
                d_med = regs[2] / DIV_DEMANDA
                d_pic = regs[3] / DIV_DEMANDA
                d_pre = regs[4] / DIV_DEMANDA
                self._atualizar_ui_demanda(d_ant, d_atu, d_med, d_pic, d_pre)

            elif janela == "fp" and len(regs) >= 4:
                fp_r = regs[0] / DIV_FP
                fp_s = regs[1] / DIV_FP
                fp_t = regs[2] / DIV_FP
                fp_tot = regs[3] / DIV_FP
                self._atualizar_ui_fp(fp_r, fp_s, fp_t, fp_tot)

        except Exception as erro:
            print(f"[Modbus] Falha na leitura ({janela}): {erro}")
            self._atualizar_status_comm(conectado=False)
            self._sinalizar_dados_desatualizados(janela)
            with self._modbus_lock:
                if self.cliente_modbus:
                    self.cliente_modbus.close()
        finally:
            self.lendo_modbus = False

    # --- Atualizações de Interface na Thread Principal ---

    @mainthread
    def _atualizar_status_comm(self, conectado: bool):
        if conectado:
            self.status_comm_texto = "COMUNICAÇÃO: ONLINE (NORMAL)"
            self.status_comm_icone = "lan-connect"
            self.status_comm_cor = [0.25, 0.25, 0.25, 1]  # Neutro em operação normal
        else:
            self.status_comm_texto = "FALHA DE COMUNICAÇÃO — DADOS DESATUALIZADOS"
            self.status_comm_icone = "alert-circle"
            self.status_comm_cor = [0.80, 0.15, 0.15, 1]  # Vermelho reservado para alarme/falha

    @mainthread
    def _sinalizar_dados_desatualizados(self, janela: str):
        if janela in self.conteudos:
            self.conteudos[janela].status_dados = "FALHA: Leitura desatualizada (sem conexão)"

    @mainthread
    def _atualizar_ui_tensoes(self, rs: float, st: float, tr: float, media: float):
        c = self.conteudos.get("tensoes")
        if not c:
            return
        c.tensao_rs = f"{rs:.1f}"
        c.tensao_st = f"{st:.1f}"
        c.tensao_tr = f"{tr:.1f}"
        c.media = f"{media:.1f}"
        c.status_dados = "Leitura atualizada (Normal)"

    @mainthread
    def _atualizar_ui_correntes(self, ir: float, is_: float, it: float, in_: float, imedia: float):
        c = self.conteudos.get("correntes")
        if not c:
            return
        c.corrente_r = f"{ir:.1f}"
        c.corrente_s = f"{is_:.1f}"
        c.corrente_t = f"{it:.1f}"
        c.corrente_n = f"{in_:.1f}"
        c.corrente_media = f"{imedia:.1f}"
        c.status_dados = "Leitura atualizada (Normal)"

    @mainthread
    def _atualizar_ui_demanda(self, ant: float, atu: float, med: float, pic: float, pre: float):
        c = self.conteudos.get("demanda")
        if not c:
            return
        c.demanda_anterior = f"{ant:.1f}"
        c.demanda_atual = f"{atu:.1f}"
        c.demanda_media = f"{med:.1f}"
        c.demanda_pico = f"{pic:.1f}"
        c.demanda_prevista = f"{pre:.1f}"
        c.status_dados = "Leitura atualizada (Normal)"

    @mainthread
    def _atualizar_ui_fp(self, fp_r: float, fp_s: float, fp_t: float, fp_tot: float):
        c = self.conteudos.get("fp")
        if not c:
            return
        c.fp_r = f"{fp_r:.3f}"
        c.fp_s = f"{fp_s:.3f}"
        c.fp_t = f"{fp_t:.3f}"
        c.fp_total = f"{fp_tot:.3f}"
        c.status_dados = "Leitura atualizada (Normal)"


if __name__ == "__main__":
    MeuSupervisorio().run()