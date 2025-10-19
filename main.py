import logging
import os
from typing import List

import discord
import docker
from discord import app_commands
from docker.errors import DockerException
from dotenv import load_dotenv

from Common.contants import APP_VERSION
from Entities.CommandExecutor import CommandExecutor
from Entities.DockerManagerClient import DockerManagerClient
from Entities.StatusRoutine import StatusRoutine

# INITIALIZATION #

# Initialize logging.
logger = logging.getLogger()
logging.basicConfig(level=logging.INFO, format='%(message)s')

# Initialize environment.
logger.info('[INFO] Updating environment variables')
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
ADMINS = str(os.getenv('ADMINS')).split(",")
GUILDS = str(os.getenv('GUILDS')).split(",")

# Set intents (permissions).
logger.info('[INFO] Setting discord intents (permissions)')
intents = discord.Intents.default()
intents.message_content = True

# Initialize discord client.
discordClient = DockerManagerClient(intents=intents, guild_ids=GUILDS)

# Initialize Docker Engine.
logger.info('[INFO] Trying to get the docker client from the environment..')

dockerClient = None
try:
    dockerClient = docker.from_env()
except DockerException as a:
    logger.error('____________________________________\n'
                 '[ERROR] Could not connect to docker. \n'
                 'Make sure that docker is running, and this app is running in the same environment.')
    logger.error(a)
    exit("Exiting application.")


@discordClient.event
async def on_ready():
    logger.info(f"[INFO] Client logged in as {discordClient.user}")
    logger.info(f"[INFO] Running version {APP_VERSION}")

    discordClient.loop.create_task(StatusRoutine(discordClient, dockerClient))
    logger.info("[INFO] Created 'container count status' loop")


# COMMANDS #

@discordClient.tree.command(name='help')
async def help_command(interaction: discord.Interaction):
    """Overview of all possible commands"""
    check_if_allowed(interaction.user.id)

    logger.info("[INFO] Executing help command.")
    executor = CommandExecutor(dockerClient, interaction=interaction)
    await executor.get_help()

    await update_container_amount()


@discordClient.tree.command(name='containers')
@app_commands.rename(container_name='container-name')
@app_commands.describe(container_name='Filter on container name')
@app_commands.describe(status='Filter on the status of a container')
async def containers_command(interaction: discord.Interaction, container_name: str = '', status: str = ''):
    """Overview of all containers. Use the filter to look for specific containers."""
    check_if_allowed(interaction.user.id)

    logger.info("[INFO] Executing container overview command.")
    executor = CommandExecutor(dockerClient, interaction=interaction)
    await executor.get_and_send_containers(filter_name=container_name, status=status)

    await update_container_amount()


@discordClient.tree.command(name='container-status')
@app_commands.rename(container_name='container-name')
@app_commands.describe(container_name='View a container')
async def container_status_command(interaction: discord.Interaction, container_name: str):
    """Overview of all containers. Use the filter to look for specific containers."""
    check_if_allowed(interaction.user.id)

    logger.info("[INFO] Executing container overview command.")
    executor = CommandExecutor(dockerClient, interaction=interaction)
    # TODO add more specific status properties
    await executor.get_and_send_containers(filter_name=container_name)

    await update_container_amount()


@discordClient.tree.command(name='container-restart')
@app_commands.rename(container_name='container-name')
@app_commands.describe(container_name='The name of the container to restart')
async def restart_command(interaction: discord.Interaction, container_name: str):
    """Restart a container."""
    check_if_allowed(interaction.user.id)

    executor = CommandExecutor(dockerClient, interaction=interaction)
    logger.info("[INFO] Executing restart container command.")
    await executor.restart_container(container_name)

    await update_container_amount()


@discordClient.tree.command(name='container-stop')
@app_commands.rename(container_name='container-name')
@app_commands.describe(container_name='The name of the container to stop')
async def stop_command(interaction: discord.Interaction, container_name: str):
    """Stop a container."""
    check_if_allowed(interaction.user.id)

    executor = CommandExecutor(dockerClient, interaction=interaction)
    logger.info("[INFO] Executing stop container command.")
    await executor.stop_container(container_name)

    await update_container_amount()


@discordClient.tree.command(name='container-rename')
@app_commands.rename(old_name='old-name')
@app_commands.describe(old_name='The name of the container to rename')
@app_commands.rename(new_name='new-name')
@app_commands.describe(new_name='The new name of the container')
async def rename_command(interaction: discord.Interaction, old_name: str, new_name: str):
    """Rename a container."""
    check_if_allowed(interaction.user.id)

    executor = CommandExecutor(dockerClient, interaction=interaction)
    logger.info("[INFO] Executing rename container command.")
    await executor.rename_container(old_name, new_name)

    await update_container_amount()


@discordClient.tree.command(name='container-remove')
@app_commands.rename(container_name='container-name')
@app_commands.describe(container_name='The name of the container to remove')
async def remove_command(interaction: discord.Interaction, container_name: str):
    """Remove a container. Warning: it cannot be recovered after."""
    check_if_allowed(interaction.user.id)

    executor = CommandExecutor(dockerClient, interaction=interaction)
    logger.info("[INFO] Executing remove container command.")
    await executor.remove_container(container_name)

    await update_container_amount()


@discordClient.tree.command(name='container-remove-range')
@app_commands.rename(container_range='container-range')
@app_commands.describe(container_range='The amount of the most recent containers to remove')
@app_commands.describe(exclude='A comma-separated string of container names to exclude. '
                               'Example: lucky_buck,magical_unicorn,bread_can')
async def remove_range_command(interaction: discord.Interaction, container_range: int, exclude: str = ""):
    """Remove a range of containers. Warning: it cannot be recovered after."""
    check_if_allowed(interaction.user.id)

    executor = CommandExecutor(dockerClient, interaction=interaction)
    logger.info("[INFO] Executing removing range of containers command.")
    await executor.remove_range_of_containers(container_range, exclude)

    await update_container_amount()


@discordClient.tree.command(name='container-logs')
@app_commands.rename(container_name='container-name')
@app_commands.describe(container_name='The name of the container to get the logs from')
@app_commands.rename(log_amount='log-amount')
@app_commands.describe(log_amount='The amount of logs to retrieve')
@app_commands.choices(log_amount=[
    app_commands.Choice(name='No limit', value=0),
    app_commands.Choice(name='50', value=50),
    app_commands.Choice(name='100', value=100),
    app_commands.Choice(name='200', value=200),
    app_commands.Choice(name='500', value=500),
    app_commands.Choice(name='1000', value=1000),
])
async def logs_command(interaction: discord.Interaction, container_name: str, log_amount: int):
    """Retrieve the recent logs of a container."""
    check_if_allowed(interaction.user.id)

    executor = CommandExecutor(dockerClient, interaction=interaction)
    logger.info("[INFO] Executing restart container command.")
    await executor.retrieve_logs_from_container(container_name, log_amount)


# Interaction with git repo's/hosted docker images #

@discordClient.tree.command(name='container-run')
@app_commands.rename(image_name='image')
@app_commands.describe(image_name='The name of the image to pull and run')
@app_commands.rename(cli_commands='cli-commands')
@app_commands.describe(cli_commands='command to run after the container started')
@app_commands.rename(container_name='container-name')
@app_commands.describe(container_name='The name to give the new container')
async def run_command(interaction: discord.Interaction, image_name: str, cli_commands: str = None, container_name: str = None):
    """Run a new container using an existing image like you would when using `docker run`."""
    executor = CommandExecutor(dockerClient, interaction=interaction)
    logger.info("[INFO] Executing run new container command.")
    await executor.run_new_container(image_name, cli_commands, container_name)

    await update_container_amount()


@discordClient.tree.command(name='container-run-from-git')
@app_commands.rename(git_repo_url='git-repo-url')
@app_commands.describe(git_repo_url='The url of the git repository')
@app_commands.rename(docker_compose_name='docker-compose-name')
@app_commands.describe(docker_compose_name='If the name of the compose file is different to "docker-compose.yml"')
async def run_from_git_command(interaction: discord.Interaction, git_repo_url: str, docker_compose_name: str = "docker-compose.yml"):
    """Deploys the app from the given git repository. The repo needs to contain a docker-compose.yml file."""
    check_if_allowed(interaction.user.id)

    executor = CommandExecutor(dockerClient, interaction=interaction)
    logger.info("[INFO] Executing deploy_from_git command.")
    await executor.deploy_from_git(git_repo_url, docker_compose_name=docker_compose_name)

    await update_container_amount()


# Autocomplete functionality #

@restart_command.autocomplete('container_name')
@stop_command.autocomplete('container_name')
@remove_command.autocomplete('container_name')
@rename_command.autocomplete('old_name')
@container_status_command.autocomplete('container_name')
@logs_command.autocomplete('container_name')
async def containers_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    executor = CommandExecutor(dockerClient, interaction=interaction)
    container_infos = await executor.get_containers_formatted()
    container_names = list(map(lambda container_info: container_info["Name"], container_infos))

    return [
        app_commands.Choice(name=container, value=container)
        for container in container_names
        if current.lower() in container.lower()
    ]


@remove_range_command.autocomplete('exclude')
async def all_containers_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    executor = CommandExecutor(dockerClient, interaction=interaction)
    container_infos = await executor.get_containers_formatted()
    container_names = list(map(lambda container_info: container_info["Name"], container_infos))

    # NOTE: isn't this lovely to look at :)
    return [
        app_commands.Choice(name=(container + ',' if current != '' else container) + current,
                            value=current + "," + container)
        for container in container_names
        if container.lower() not in current.lower() or current == ""
    ]


@containers_command.autocomplete("status")
async def containers_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name=status, value=status)
        for status in ["running", "paused", "exited", "restarting"]
        if current in status
    ]


def check_if_allowed(user_id):
    user_id = str(user_id)
    if user_id not in ADMINS:
        logger.warning("[INFO] Container overview command called by non-admin.")
        raise Exception(f"Nuh-uh: user {user_id} is not a registered admin.")


async def update_container_amount():
    executor = CommandExecutor(dockerClient)
    running, total = await executor.get_running_total_containers()

    await discordClient.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name=f"{running} of {total} containers running")
    )


try:
    discordClient.run(TOKEN)
except TypeError:
    logger.error("[ERROR] Could not start the discord client. Make sure you have all the necessary env variables.")
