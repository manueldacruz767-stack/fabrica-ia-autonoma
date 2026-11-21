import textwrap

LARGURA_A4 = 595.28
ALTURA_A4 = 841.89
MARGEM = 56
TAMANHO_TITULO = 18
TAMANHO_CORPO = 11
ESPACO_LINHA = 17
LIMITE_LINHA = 88
TITULO = "RECIBO DE SALARIO"

ROTULOS = (
    ("id", "Identificador"),
    ("funcionario", "Funcionario"),
    ("mes", "Mes"),
    ("salario_base", "Salario base"),
    ("descontos", "Descontos"),
    ("liquido", "Liquido"),
    ("estado", "Estado"),
    ("criado_por", "Criado por"),
    ("criado_em", "Criado em"),
)


def escapar_texto_pdf(texto: object) -> bytes:
    codificado = str(texto if texto is not None else "").encode("cp1252", errors="replace")
    resultado = bytearray()
    for byte in codificado:
        if byte in (0x28, 0x29, 0x5C):
            resultado.extend(b"\\" + bytes([byte]))
        elif byte < 32:
            resultado.extend(f"\\{byte:03o}".encode("ascii"))
        else:
            resultado.append(byte)
    return bytes(resultado)


def quebrar_texto(texto: object, limite: int = LIMITE_LINHA) -> list[str]:
    return textwrap.wrap(
        str(texto if texto is not None else ""),
        width=limite,
        break_long_words=True,
        break_on_hyphens=False,
    ) or [""]


def formatar_valor(valor: object) -> str:
    if isinstance(valor, float):
        return f"{valor:.2f}"
    return str(valor if valor is not None else "")


def escrever_texto(conteudo: bytearray, texto: object, x: float, y: float, fonte: str = "F1", tamanho: int = TAMANHO_CORPO) -> None:
    conteudo.extend(f"BT /{fonte} {tamanho} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm (".encode("ascii"))
    conteudo.extend(escapar_texto_pdf(texto))
    conteudo.extend(b") Tj ET\n")


def construir_conteudo(dados: dict) -> bytes:
    conteudo = bytearray()
    y = ALTURA_A4 - MARGEM
    escrever_texto(conteudo, TITULO, MARGEM, y, "F2", TAMANHO_TITULO)
    y -= ESPACO_LINHA * 2

    linhas = []
    for chave, rotulo in ROTULOS:
        if chave in dados and dados[chave] not in (None, ""):
            linhas.append(f"{rotulo}: {formatar_valor(dados[chave])}")
    for chave, valor in dados.items():
        if chave not in dict(ROTULOS) and valor not in (None, ""):
            linhas.append(f"{chave.replace('_', ' ').title()}: {formatar_valor(valor)}")

    for linha in linhas:
        partes = quebrar_texto(linha)
        for indice, parte in enumerate(partes):
            if y < MARGEM + ESPACO_LINHA:
                break
            escrever_texto(conteudo, parte if indice == 0 else f"   {parte}", MARGEM, y)
            y -= ESPACO_LINHA
        y -= ESPACO_LINHA / 2

    escrever_texto(conteudo, "Documento gerado pelo HIS - Hospital Publico", MARGEM, MARGEM / 2, "F2", 9)
    return bytes(conteudo)


def montar_documento(objetos: list[bytes]) -> bytes:
    documento = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    deslocamentos = [0]
    for numero, objeto in enumerate(objetos, 1):
        deslocamentos.append(len(documento))
        documento.extend(f"{numero} 0 obj\n".encode("ascii"))
        documento.extend(objeto)
        documento.extend(b"\nendobj\n")
    inicio_xref = len(documento)
    documento.extend(f"xref\n0 {len(objetos) + 1}\n".encode("ascii"))
    documento.extend(b"0000000000 65535 f \n")
    for deslocamento in deslocamentos[1:]:
        documento.extend(f"{deslocamento:010d} 00000 n \n".encode("ascii"))
    documento.extend(
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n"
        f"startxref\n{inicio_xref}\n%%EOF\n".encode("ascii")
    )
    return bytes(documento)


def gerar_pdf_recibo(dados: dict) -> bytes:
    conteudo = construir_conteudo(dados)
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {LARGURA_A4:.2f} {ALTURA_A4:.2f}] "
            "/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>"
        ).encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
        f"<< /Length {len(conteudo)} >>\nstream\n".encode("ascii") + conteudo + b"endstream",
    ]
    return montar_documento(objetos)
