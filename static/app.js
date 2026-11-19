// Troca de abas na tela de resultado.
document.querySelectorAll(".abas button").forEach((botao) => {
  botao.addEventListener("click", () => {
    document.querySelectorAll(".abas button, .aba").forEach((el) => el.classList.remove("ativa"));
    botao.classList.add("ativa");
    document.getElementById(botao.dataset.aba).classList.add("ativa");
  });
});

// Botão "Copiar mensagem" da régua de cobrança.
document.querySelectorAll(".copiar").forEach((botao) => {
  botao.addEventListener("click", async () => {
    await navigator.clipboard.writeText(botao.dataset.texto);
    botao.textContent = "Copiado ✓";
    setTimeout(() => (botao.textContent = "Copiar mensagem"), 2000);
  });
});
