from kivymd.app import MDApp
from kivymd.uix.button import MDFlatButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.boxlayout import MDBoxLayout
from kivy.properties import StringProperty
from kivy.clock import Clock

# Classe que controla os dados dentro da janela
class JanelaTensoesContent(MDBoxLayout):
    tensao_rs = StringProperty("0.0")
    tensao_st = StringProperty("0.0")
    tensao_tr = StringProperty("0.0")

class MeuSupervisorio(MDApp):
    dialog_tensoes = None
    evento_atualizacao = None

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
                        on_release=self.fechar_janela_tensoes
                    ),
                ],
            )
        
        self.dialog_tensoes.open()
        # Inicia a atualização em tempo real (ex: a cada 1 segundo)
        self.evento_atualizacao = Clock.schedule_interval(self.atualizar_valores_tensoes, 1)

    def fechar_janela_tensoes(self, *args):
        self.dialog_tensoes.dismiss()
        # Para a atualização dos dados quando a janela fecha para não sobrecarregar
        if self.evento_atualizacao:
            self.evento_atualizacao.cancel()

    def atualizar_valores_tensoes(self, *args):
        # Aqui você substitui pela sua função real de leitura do PyModbus
        # Exemplo: valores = cliente_modbus.read_holding_registers(847, 3)
        # Lembre-se que o Divisor é 10 (ex: leitura 3805 = 380.5 V)
        
        leitura_rs = 3805  # Simulação do endereço 847
        leitura_st = 3798  # Simulação do endereço 848
        leitura_tr = 3811  # Simulação do endereço 849

        self.conteudo_tensoes.tensao_rs = f"{(leitura_rs / 10.0):.1f}"
        self.conteudo_tensoes.tensao_st = f"{(leitura_st / 10.0):.1f}"
        self.conteudo_tensoes.tensao_tr = f"{(leitura_tr / 10.0):.1f}"