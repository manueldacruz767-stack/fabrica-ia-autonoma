from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app import db
from app.pdf import gerar_pdf_recibo
from app.security import exigir

router = APIRouter(prefix="/api/recibos", tags=["relatorios"])


@router.get("/{folha_id}/pdf")
def recibo_pdf(folha_id: str, usuario: dict = Depends(exigir("rh", "administrador", "auditoria"))) -> Response:
    conexao = db.ligacao()
    try:
        folha = conexao.execute("SELECT * FROM folhas_salario WHERE id = ?", (folha_id,)).fetchone()
    finally:
        conexao.close()
    if not folha:
        raise HTTPException(status_code=404, detail="Folha nao encontrada")
    nome_arquivo = "".join(caractere if caractere.isalnum() or caractere in "-_" else "_" for caractere in folha_id)
    return Response(
        content=gerar_pdf_recibo(dict(folha)),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="recibo-{nome_arquivo}.pdf"'},
    )
