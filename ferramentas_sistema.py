import subprocess

def executar_comando_sistema(comando: str) -> str:
    """Executa um comando seguro no terminal do Fedora e devolve a saída ou o erro."""
    try:
        resultado = subprocess.run(
            comando, 
            shell=True, 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True,
            timeout=60
        )
        saida = resultado.stdout.strip()
        return saida if saida else "Comando executado com sucesso (sem output)." 
    except subprocess.CalledProcessError as e:
        return f"Erro ao executar o comando:\nSTDOUT: {e.stdout}\nSTDERR: {e.stderr}"
    except subprocess.TimeoutExpired:
        return "Erro: O comando excedeu o tempo limite de execução (60 segundos)."
    except Exception as e:
        return f"Erro inesperado: {str(e)}"

if __name__ == "__main__":
    print("Módulo de ferramentas de sistema carregado.")
