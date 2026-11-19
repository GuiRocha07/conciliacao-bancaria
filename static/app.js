// Troca de abas na tela de resultado.
document.querySelectorAll(".abas button").forEach((botao) => {
  botao.addEventListener("click", () => {
    document.querySelectorAll(".abas button, .aba").forEach((el) => el.classList.remove("ativa"));
    botao.classList.add("ativa");
    document.getElementById(botao.dataset.aba).classList.add("ativa");
  });
});
