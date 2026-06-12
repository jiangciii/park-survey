const loginForm = document.getElementById("loginForm");
const loginError = document.getElementById("loginError");
const runtimeHint = document.getElementById("runtimeHint");

if (window.location.protocol === "file:") {
  runtimeHint.textContent = "当前是直接打开本地 HTML。管理员后台必须通过 survey_server.py 启动后访问 /admin/login 才能登录。";
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginError.textContent = "";
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;

  try {
    const response = await fetch("/api/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ username, password }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || "登录失败");
    window.location.href = "/admin/dashboard";
  } catch (error) {
    loginError.textContent = error.message;
  }
});
