import subprocess

def verificar_ferramenta(comando: str, nome: str):
    """Verifica se uma ferramenta CLI está instalada e acessível."""
    try:
        resultado = subprocess.run(
            comando, 
            shell=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True,
            timeout=10
        )
        if resultado.returncode == 0:
            print(f"[VERIFICADO] {nome} está instalado: {resultado.stdout.splitlines()[0]}")
            return True
        else:
            print(f"[FALHA] {nome} não está a responder corretamente.")
            return False
    except Exception:
        print(f"[FALHA] {nome} não encontrado no sistema.")
        return False

def testar_autenticacoes():
    print("=== A VERIFICAR PRONTIDÃO DE INFRAESTRUTURA DOS AGENTES ===")
    
    # 1. Verificar Git
    verificar_ferramenta("git --version", "Git")
    
    # 2. Verificar GitHub CLI (para criar repositórios automaticamente)
    verificar_ferramenta("gh --version", "GitHub CLI (gh)")
    
    # 3. Verificar Vercel CLI (para fazer deployments automáticos)
    verificar_ferramenta("vercel --version", "Vercel CLI")

    print("=" * 60)

if __name__ == "__main__":
    testar_autenticacoes()
